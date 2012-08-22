import cosmology
import defaults
import hod
import mass_function
import numpy
from scipy import integrate
from scipy import special
from scipy.interpolate import InterpolatedUnivariateSpline

"""Classes for describing a basic halo model.

Given an input HOD object and cosmological and halo parameters, a halo object
should be able to generate a non-linear power spectrum for dark matter,
galaxies or their cross-spectrum.  It should also be able to return the halo
profile as a function of mass and radius and its Fourier transform as a
function of mass and wave-number.
"""

__author__ = ("Chris Morrison <morrison.chrisb@gmail.com>"+
              "Ryan Scranton <ryan.scranton@gmail.com>, ")

class Halo(object):
    """Basic halo model object.

    Given an HOD object and cosmological and halo parameters, a halo object
    should be able to generate a non-linear power spectrum for dark matter,
    galaxies or their cross-spectrum.  It should also be able to return
    the halo profile as a function of mass and radius and its Fourier transform
    as a function of mass and wave-number.

    Attributes:
         redshift: float redshift at which to compute the halo model
         input_hod: HOD object from hod.py. Determines how galaxies populate 
             halos
         cosmo_single_epoch: SingleEpoch object from cosmology.py
         mass_func: MassFunction object from mass_function.py
         halo_dict: dictionary of floats defining halo properties. (see 
             defaults.py for details)
    """
    def __init__(self, redshift=0.0, input_hod=None, cosmo_single_epoch=None,
                 mass_func=None, halo_dict=None, **kws):
        # Hard coded, but we shouldn't expect halos outside of this range.
        self._k_min = 0.001
        self._k_max = 100.0
        ln_mass_min = numpy.log(1.0e9)
        ln_mass_max = numpy.log(5.0e16)
        
        self._ln_k_max = numpy.log(self._k_max)
        self._ln_k_min = numpy.log(self._k_min)

        self._ln_k_array = numpy.linspace(
            self._ln_k_min, self._ln_k_max,
            defaults.default_precision["halo_npoints"])

        self._redshift = redshift

        if cosmo_single_epoch is None:
            cosmo_single_epoch = cosmology.SingleEpoch(redshift)
        self.cosmo = cosmo_single_epoch

        if halo_dict is None:
            halo_dict = defaults.default_halo_dict
        self.halo_dict = halo_dict

        if mass_func is None:
            mass_func = mass_function.MassFunction(
                self._redshift, self.cosmo, self.halo_dict)
        self.mass = mass_func

        self.c0 = halo_dict["c0"]/(1.0 + self._redshift)
        self.beta = halo_dict["beta"]

        # If we hard-code to an NFW profile, then we can use an analytic
        # form for the halo profile Fourier transform.
        # self.alpha = -1.0*halo_dict.dpalpha
        self.alpha = -1.0

        #self.cosmo = cosmology.SingleEpoch(self._redshift, cosmo_dict)
        self.delta_v = self.cosmo.delta_v()
        self.rho_bar = self.cosmo.rho_bar()
        self._h = self.cosmo._h

        if input_hod is None:
            input_hod = hod.HODZheng()
        self.local_hod = input_hod
    
        self._calculate_n_bar()
        self._initialize_halo_splines()

        self._initialized_h_m = False
        self._initialized_h_g = False

        self._initialized_pp_mm = False
        self._initialized_pp_gm = False
        self._initialized_pp_gg = False

    def set_cosmology(self, cosmo_dict, redshift=None):
        """
        Reset the internal cosmology to the values in cosmo_dict and 
        re-initialize the internal splines. Optimally reset the internal
        redshift value.

        Args:
            cosmo_dict: dictionary of floats defining a cosmology. (see
                defaults.py for details)
            redshift: float redshift to compute halo model.
        """
        if redshift==None:
            redshift = self._redshift
        self.cosmo_dict = cosmo_dict
        self._redshift = redshift
        self.cosmo = cosmology.SingleEpoch(redshift, cosmo_dict)
        self.delta_v = self.cosmo.delta_v()
        self.rho_bar = self.cosmo.rho_bar()
        self._h = self.cosmo._h

        self.c0 = self.halo_dict["c0"]/(1.0 + redshift)

        self.mass.set_cosmology_object(self.cosmo)

        self._calculate_n_bar()
        self._initialize_halo_splines()

        self._initialized_h_m = False
        self._initialized_h_g = False

        self._initialized_pp_mm = False
        self._initialized_pp_gm = False
        self._initialized_pp_gg = False

    def set_hod(self, input_hod):
        """
        Reset the internal HOD object to input_hod and re-initialize splines.

        Args:
            input_hod: a HOD object from hod.py defining the occupation
                distribution of galaxies.
        """
        self.local_hod = input_hod

        self._calculate_n_bar()

        self._initialized_h_g = False

        self._initialized_pp_mm = False
        self._initialized_pp_gm = False
        self._initialized_pp_gg = False

    def set_halo(self, halo_dict=None):
        """
        Reset the internal halo properties to the values in halo_dict and 
        re-initialize the class splines.

        Args:
            halo_dict: dictionary of floats defining halo properties. (see
                defaults.py for details)
        """
        self.c0 = halo_dict["c0"]/(1.0 + self._redshift)
        self.beta = halo_dict["beta"]
        self.alpha = -1.0

        self.mass.set_halo(halo_dict)

        
        self.set_hod(self.local_hod)
        
    def set_redshift(self, redshift):
        """
        Reset the internal redshift to the value redshift and 
        re-initialize the class splines.

        Args:
            redshift: float value redshift at which to compute the halo model
        """
        if redshift != self._redshift:
            self.set_cosmology(self.cosmo.cosmo_dict, redshift)

    def linear_power(self, k):
        """
        Linear power spectrum from the cosmology module.

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array linear power spectrum [Mpc/h]**3
        """
        return self.cosmo.linear_power(k)

    def power_mm(self, k):
        """
        Non-Linear matter power spectrum derived from the halo model. This power
        spectrum should be used for correlations that depend only on dark matter
        (ie cosmo shear and magnification).

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear matter power spectrum [Mpc/h]**3
        """
        if not self._initialized_h_m:
            self._initialize_h_m()
        if not self._initialized_pp_mm:
            self._initialize_pp_mm()

        ### first term in the this function is what is usually referred to as
        ### the 2_halo term (ie correltaions between different halos). The
        ### second term (_pp_mm) is referred to as the 1_halo or poisson term
        ### (ie correlations within a halo).
        return self.linear_power(k)*self._h_m(k)*self._h_m(k) + self._pp_mm(k)

    def power_gm(self, k):
        """
        Non-Linear galaxy-matter cross power spectrum derived from the halo
        model and input halo occupation distribution.This power spectrum should
        be used for correlations that depend on the cross-correlation between
        galaxies and dark matter.
        (ie galaxy-galaxy shear and magnification).

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear galaxy-matter power spectrum [Mpc/h]**3
        """
        if not self._initialized_h_m:
            self._initialize_h_m()
        if not self._initialized_h_g:
            self._initialize_h_g()
        if not self._initialized_pp_gm:
            self._initialize_pp_gm()

        return self.linear_power(k)*self._h_g(k)*self._h_m(k) + self._pp_gm(k)

    def power_mg(self, k):
        """
        Non-Linear galaxy-matter cross power spectrum derived from the halo
        model and input halo occupation distribution. This power spectrum 
        should be used for correlations between galaxies and matter.
        themselves. (ie galaxy clustering/auto-correlations)

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear galaxy-matter power spectrum [Mpc/h]**3
        """
        return self.power_gm(k)

    def power_gg(self, k):
        """
        Non-Linear galaxy power spectrum derived from the halo
        model and input halo occupation distribution.

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear galaxy power spectrum [Mpc/h]**3
        """
        if not self._initialized_h_g:
            self._initialize_h_g()
        if not self._initialized_pp_gg:
            self._initialize_pp_gg()

        return self.linear_power(k)*self._h_g(k)*self._h_g(k) + self._pp_gg(k)

    def virial_radius(self, mass):
        """
        Halo virial radius in Mpc as a function of mass in M_sun.

        Args:
            mass: float array of halo mass [M_solar/h]
        Returns:
            float array virial radius [Mpc/h]
        """
        return numpy.exp(self._ln_r_v_spline(numpy.log(mass)))

    def concentration(self, mass):
        """
        Halo concentration as a function of mass in M_sun.
        
        Functional form from Bullock et al.

        Args:
            mass: float array of halo mass [M_solar/h]
        Returns:
            float array halo concentration
        """
        return numpy.exp(self._ln_concen_spline(numpy.log(mass)))

    def halo_normalization(self, mass):
        """
        Halo normalization in h^2*M_sun/Mpc^3 as a function of mass in M_sun.

        Args:
            mass: float array of halo mass [M_solar/h]
        Returns:
            float array halo normalization
        """
        return numpy.exp(self._ln_halo_norm_spline(numpy.log(mass)))

    def y(self, ln_k, mass):
        """Fourier transform of the halo profile.

        Using an analytic expression for the Fourier transform from
        White (2001).  This is only valid for an NFW profile.

        Args:
            ln_k: float array natural log wave number [ln(Mpc/h)]
            mass: float halo mass [M_solar/h]
        Returns:
            float array NFW profile Fourier transform
        """

        k = numpy.exp(ln_k)/self._h
        con = self.concentration(mass)
        con_plus = 1.0 + con
        z = k*self.virial_radius(mass)/con
        si_z, ci_z = special.sici(z)
        si_cz, ci_cz = special.sici(con_plus*z)
        rho_km = (numpy.cos(z)*(ci_cz - ci_z) +
                  numpy.sin(z)*(si_cz - si_z) -
                  numpy.sin(con*z)/(con_plus*z))
        mass_k = numpy.log(con_plus) - con/con_plus

        return rho_km/mass_k

    def write(self, output_file_name):
        """
        Write out all halo model power spectra to a file.

        Args:
            output_file_name: string name of file to write to
        """
        f = open(output_file_name, "w")
        f.write("#ttype1 = k [Mpc/h]\n#ttype2 = linear_power [(Mpc/h)^3]\n"
                "#ttype3 = power_mm\n#ttype4 = power_gg\n"
                "#ttype5 = power_gm\n")
        for ln_k in self._ln_k_array:
            k = numpy.exp(ln_k)
            f.write("%1.10f %1.10f %1.10f %1.10f %1.10f\n" % (
                k, self.linear_power(k), self.power_mm(k),
                self.power_gg(k), self.power_gm(k)))
        f.close()

    def write_halo(self, output_file_name, k=None):
        """
        Write out halo properties as a functino of mass [Mpc/h].

        Args:
            output_file_name: string name of file to write to
        """
        if k is None:
            k = 0.01
        ln_k = numpy.log(k)

        f = open(output_file_name, "w")
        f.write("#ttype1 = mass [M_solar/h]\n"
                "#ttype2 = y(k, M), NFW Fourier Transform\n"
                "#ttype3 = concentration\n#ttype4 = halo_norm\n"
                "#ttype5 = virial_mass [M_solar/h]\n")
        for nu in self.mass._nu_array:
            mass = self.mass.mass(nu)
            f.write("%1.10f %1.10f %1.10f %1.10f %1.10f\n" % (
                mass, self.y(ln_k, mass), self.concentration(mass),
                self.halo_normalization(mass), self.virial_radius(mass)))
        f.close()

    def write_power_components(self, output_file_name):
        """
        Write out the individual components from the halo model [Mpc/h].

        Args:
            output_file_name: string name of file to write to
        """
        f = open(output_file_name, "w")
        f.write("#ttype1 = k [Mpc/h]\n#ttype2 = 2 halo dark matter component\n"
                "#ttype3 = dark matter poisson component\n"
                "#ttype4 = 2 halo galaxy component\n"
                "#ttype5 = matter-galaxy poisson component\n"
                "#ttype6 = galaxy-galaxy poisson component\n")
        for ln_k in self._ln_k_array:
            k = numpy.exp(ln_k)
            f.write("%1.10f %1.10f %1.10f %1.10f %1.10f %1.10f\n" % (
                k, self._h_m(k), self._pp_mm(k),
                self._h_g(k), self._pp_gm(k), self._pp_gg(k)))
        f.close()

    def _h_m(self, k):
        return numpy.where(
            numpy.logical_and(k >= self._k_min, k <= self._k_max),
            self._h_m_spline(numpy.log(k)), 0.0)

    def _pp_mm(self, k):
        return numpy.where(
            numpy.logical_and(k >= self._k_min, k <= self._k_max),
            self._pp_mm_spline(numpy.log(k)), 0.0)

    def _pp_gm(self, k):
        return numpy.where(
            numpy.logical_and(k >= self._k_min, k <= self._k_max),
            self._pp_gm_spline(numpy.log(k)), 0.0)

    def _h_g(self, k):
        return numpy.where(
            numpy.logical_and(k >= self._k_min, k <= self._k_max),
            self._h_g_spline(numpy.log(k)), 0.0)

    def _pp_gg(self, k):
        return numpy.where(
            numpy.logical_and(k >= self._k_min, k <= self._k_max),
            self._pp_gg_spline(numpy.log(k)), 0.0)

    def _calculate_n_bar(self):
        nu_min = self.mass.nu_min
        if (self.local_hod.first_moment_zero > -1 and 
            self.local_hod.first_moment_zero >
            numpy.exp(self.mass.ln_mass_min)):
            nu_min = self.mass.nu(self.local_hod.first_moment_zero)
        
        self.n_bar_over_rho_bar = integrate.romberg(
            self._nbar_integrand, numpy.log(nu_min),
            numpy.log(self.mass.nu_max), vec_func=True,
            tol=defaults.default_precision["global_precision"],
            rtol=defaults.default_precision["halo_precision"],
            divmax=defaults.default_precision["divmax"])

        self.n_bar = self.n_bar_over_rho_bar*self.rho_bar

    def _nbar_integrand(self, ln_nu):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)

        return nu*self.local_hod.first_moment(mass)*self.mass.f_nu(nu)/mass

    def calculate_bias(self):
        """
        Compute the average galaxy bias from the input HOD. The output value is
        stored in the class variable bias.
        
        Returns:
            float bias
        """
        self.bias = integrate.romberg(
            self._bias_integrand, numpy.log(self.mass.nu_min), 
            numpy.log(self.mass.nu_max), vec_func=True,
            tol=defaults.default_precision["global_precision"],
            rtol=defaults.default_precision["halo_precision"],
            divmax=defaults.default_precision["divmax"])

        self.bias = self.bias/self.n_bar_over_rho_bar
        return self.bias

    def _bias_integrand(self, ln_nu):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)

        return (nu*self.local_hod.first_moment(mass)*self.mass.f_nu(nu)*
                self.mass.bias_nu(nu)/mass)

    def calculate_m_eff(self):
        """
        Compute the effective Halo mass from the input HOD. The output value is
        stored in the class variable m_eff.
        
        Returns:
            float m_eff
        """
        self.m_eff = integrate.romberg(
            self._m_eff_integrand, numpy.log(self.mass.nu_min), 
            numpy.log(self.mass.nu_max), vec_func=True,
            tol=defaults.default_precision["global_precision"],
            rtol=defaults.default_precision["halo_precision"],
            divmax=defaults.default_precision["divmax"])

        self.m_eff = self.m_eff/self.n_bar_over_rho_bar

        return self.m_eff

    def _m_eff_integrand(self, ln_nu):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)

        return nu*self.local_hod.first_moment(mass)*self.mass.f_nu(nu)

    def calculate_f_sat(self):
        """
        Compute the fraction of satellite galaxies relative to the total number.
        This function requires the hod object to have a satellite_first_moment
        method. Raises AttributeError if no such method is found. Stores the
        result in the class variable f_sat.
        
        Returns:
            float f_sat
        """
        self.f_sat= integrate.romberg(
            self._f_sat_integrand, numpy.log(self.mass.nu_min), 
            numpy.log(self.mass.nu_max), vec_func=True,
            tol=defaults.default_precision["global_precision"],
            rtol=defaults.default_precision["halo_precision"],
            divmax=defaults.default_precision["divmax"])

        self.f_sat = self.f_sat/self.n_bar_over_rho_bar

        return self.f_sat

    def _f_sat_integrand(self, ln_nu):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)

        return (nu*self.local_hod.satellite_first_moment(mass)*
                self.mass.f_nu(nu)/mass)

    def _initialize_halo_splines(self):
        ln_r_v_array = numpy.zeros_like(self.mass._nu_array)
        ln_concen_array = numpy.zeros_like(self.mass._nu_array)
        ln_halo_norm_array = numpy.zeros_like(self.mass._nu_array)

        for idx in xrange(self.mass._nu_array.size):
            mass = numpy.exp(self.mass._ln_mass_array[idx])
            ln_r_v_array[idx] = numpy.log(self._virial_radius(mass))
            ln_concen_array[idx] = numpy.log(self._concentration(mass))
            ln_halo_norm_array[idx] = numpy.log(self._halo_normalization(mass))

        self._ln_r_v_spline = InterpolatedUnivariateSpline(
            self.mass._ln_mass_array, ln_r_v_array)
        self._ln_concen_spline = InterpolatedUnivariateSpline(
            self.mass._ln_mass_array, ln_concen_array)
        self._ln_halo_norm_spline = InterpolatedUnivariateSpline(
            self.mass._ln_mass_array, ln_halo_norm_array)

    # def _a_c(self, mass):
    #     """Formation epoch definition from Wechsler et al. 2002
    #     """
    #     a_c = 0.1*numpy.log10(mass)-0.9
    #     if a_c > 0.01:
    #         return 0.1*numpy.log10(mass)-0.9
    #     elif a_c <=0.01:
    #         return 0.01

    # def _concentration(self, mass):
    #     """Halo concentration as a function of halo mass.

    #     Functional form from Wechsler et al. 2002
    #     """
    #     return 4.1/(self._a_c(mass)*(1+self._redshift))

    def _concentration(self, mass):
        """Halo concentration as a function of halo mass.

        Functional form from Bullock et al.
        """
        return self.c0*(mass/self.mass.m_star)**self.beta
        
    def _halo_normalization(self, mass):
        """Halo normalization as a function of mass.

        The halo density profile is normalized such that the integral of the
        density profile out to the virial radius equals the halo mass.  This
        ends up being the ratio between the halo mass and the integral

        int(0, concentration, x**(2+alpha)/(1 + x)**(3+alpha))

        which is a hypergeometric function of alpha and the concentration.
        """
        con = self._concentration(mass)
        rho_s = (self.rho_bar*self.delta_v*con*con*con)/3.0
        rho_norm = (con**(3.0 + self.alpha)*
                    special.hyp2f1(3.0+self.alpha, 3.0+self.alpha,
                                   4.0+self.alpha, -1.0*con))/(3.0+self.alpha)

        return rho_s/rho_norm

    def _virial_radius(self, mass):
        """Halo virial radius as a function of mass."""
        r3 = 3.0*mass/(4.0*numpy.pi*self.delta_v*self.rho_bar)
        return r3**(1.0/3.0)

    def _initialize_h_m(self):
        h_m_array = numpy.zeros_like(self._ln_k_array)

        for idx in xrange(self._ln_k_array.size):
            h_m = integrate.romberg(
                self._h_m_integrand, numpy.log(self.mass.nu_min),
                numpy.log(self.mass.nu_max), vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["halo_precision"],
                divmax=defaults.default_precision["divmax"],
                args=(self._ln_k_array[idx],))
            h_m_array[idx] = h_m

        self._h_m_spline = InterpolatedUnivariateSpline(
            self._ln_k_array, h_m_array)
        self._initialized_h_m = True

    def _h_m_integrand(self, ln_nu, ln_k):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)

        return nu*self.mass.f_nu(nu)*self.mass.bias_nu(nu)*self.y(ln_k, mass)

    def _initialize_h_g(self):
        h_g_array = numpy.zeros_like(self._ln_k_array)
        
        ### To make the romberg intergration more effecient we use an internal
        ### HOD variable to tell the code the limit below which the selected
        ### moment is zero.
        nu_min = self.mass.nu_min
        if (self.local_hod.first_moment_zero > -1 and
            self.local_hod.first_moment_zero >
            numpy.exp(self.mass.ln_mass_min)):
            nu_min = self.mass.nu(self.local_hod.first_moment_zero)
        for idx in xrange(self._ln_k_array.size):
            h_g = integrate.romberg(
                self._h_g_integrand, numpy.log(self.mass.nu_min),
                numpy.log(self.mass.nu_max), vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["halo_precision"],
                divmax=defaults.default_precision["divmax"],
                args=(self._ln_k_array[idx],))
            # h_g = integrate.quad(
            #     self._h_g_integrand, numpy.log(nu_min),
            #     numpy.log(self.mass.nu_max),
            #     args=(self._ln_k_array[idx],),
            #     limit=defaults.default_precision["halo_limit"])[0]
            
            ### We move the mass density normalization into the integrand here
            ### to prevent romberg having to integrate very small values.
            h_g_array[idx] = h_g

        self._h_g_spline = InterpolatedUnivariateSpline(
            self._ln_k_array, h_g_array)
        self._initialized_h_g = True

    def _h_g_integrand(self, ln_nu, ln_k):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)

        return (nu*self.mass.f_nu(nu)*self.mass.bias_nu(nu)*
                self.y(ln_k, mass)*self.local_hod.first_moment(mass)/(
                mass*self.n_bar_over_rho_bar))

    def _initialize_pp_mm(self):
        pp_mm_array = numpy.zeros_like(self._ln_k_array)

        for idx in xrange(self._ln_k_array.size):
            pp_mm = integrate.romberg(
                self._pp_mm_integrand, numpy.log(self.mass.nu_min),
                numpy.log(self.mass.nu_max), vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["halo_precision"],
                divmax=defaults.default_precision["divmax"],
                args=(self._ln_k_array[idx],))
            pp_mm_array[idx] = pp_mm/self.rho_bar

        self._pp_mm_spline = InterpolatedUnivariateSpline(
            self._ln_k_array, pp_mm_array)
        self._initialized_pp_mm = True

    def _pp_mm_integrand(self, ln_nu, ln_k):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)
        y = self.y(ln_k, mass)

        return nu*self.mass.f_nu(nu)*mass*y*y

    def _initialize_pp_gg(self):
        pp_gg_array = numpy.zeros_like(self._ln_k_array)

        ### To make the romberg intergration more effecient we use an internal
        ### HOD variable to tell the code the limit below which the selected
        ### moment is zero.
        nu_min = self.mass.nu_min
        if (self.local_hod.second_moment_zero > -1 and
            self.local_hod.second_moment_zero >
            numpy.exp(self.mass.ln_mass_min)):
            nu_min = self.mass.nu(self.local_hod.second_moment_zero)
        ### Some Numerical Differnce between romberg and quad here.
        for idx in xrange(self._ln_k_array.size):
            pp_gg = integrate.romberg(
                self._pp_gg_integrand, numpy.log(nu_min),
                numpy.log(self.mass.nu_max), vec_func=True,
                args=(self._ln_k_array[idx],),
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["halo_precision"],
                divmax=defaults.default_precision["divmax"])
            # pp_gg = integrate.quad(
            #     self._pp_gg_integrand, numpy.log(self.mass.nu_min),
            #     numpy.log(self.mass.nu_max),
            #     args=(self._ln_k_array[idx],),
            #     limit=defaults.default_precision["halo_limit"])[0]
            
            ### We move the mass density normalization into the integrand here
            ### to prevent romberg having to integrate very small values.
            pp_gg_array[idx] = pp_gg*self.rho_bar

        self._pp_gg_spline = InterpolatedUnivariateSpline(
            self._ln_k_array, pp_gg_array)
        self._initialized_pp_gg = True

    def _pp_gg_integrand(self, ln_nu, ln_k):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)
        y = self.y(ln_k, mass)
        n_pair = self.local_hod.second_moment(mass)

        return numpy.where(
            n_pair < 1,
            nu*self.mass.f_nu(nu)*n_pair*y/(mass*self.n_bar*self.n_bar),
            nu*self.mass.f_nu(nu)*n_pair*y*y/(mass*self.n_bar*self.n_bar))

    def _initialize_pp_gm(self):
        pp_gm_array = numpy.zeros_like(self._ln_k_array)

        ### To make the romberg intergration more effecient we use an internal
        ### HOD variable to tell the code the limit below which the selected
        ### moment is zero.
        nu_min = self.mass.nu_min
        if (self.local_hod.first_moment_zero > -1 and
            self.local_hod.first_moment_zero >
            numpy.exp(self.mass.ln_mass_min)):
            nu_min = self.mass.nu(self.local_hod.first_moment_zero)
        ### Some Numerical Differences between romberg and Quad here.
        for idx in xrange(self._ln_k_array.size):
            pp_gm = integrate.romberg(
                self._pp_gm_integrand, numpy.log(nu_min),
                numpy.log(self.mass.nu_max), vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["halo_precision"],
                args=(self._ln_k_array[idx],),
                divmax=defaults.default_precision["divmax"])
            # pp_gm, pp_gm_err = integrate.quad(
            #     self._pp_gm_integrand, numpy.log(nu_min),
            #     numpy.log(self.mass.nu_max),
            #     limit=defaults.default_precision["halo_limit"],
            #     args=(self._ln_k_array[idx],))
            pp_gm_array[idx] = pp_gm/self.n_bar

        self._pp_gm_spline = InterpolatedUnivariateSpline(
            self._ln_k_array, pp_gm_array)
        self._initialized_pp_gm = True

    def _pp_gm_integrand(self, ln_nu, ln_k):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)
        y = self.y(ln_k, mass)
        n_exp = self.local_hod.first_moment(self.mass.mass(nu))

        return numpy.where(n_exp < 1,
                           nu*self.mass.f_nu(nu)*n_exp*y,
                           nu*self.mass.f_nu(nu)*n_exp*y*y)


class HaloExclusion(Halo):

    def __init__(self, redshift=0.0, input_hod=None, cosmo_single_epoch=None,
                 mass_func=None, halo_dict=None, **kws):
        Halo.__init__(self, redshift, input_hod, cosmo_single_epoch,
                      mass_func, halo_dict, **kws)

    def power_gm(self, k):
        """
        Non-Linear galaxy power spectrum derived from the halo
        model and input halo occupation distribution.

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear galaxy power spectrum [Mpc/h]**3
        """
        if not self._initialized_h_g:
            self._initialize_h_g()
        if not self._initialized_pp_gg:
            self._initialize_pp_gm()

        return self.power_mm(k)*self._h_g(k)*self._h_m(k) + self._pp_gm(k)

    def power_mg(self, k):
        """
        Non-Linear galaxy power spectrum derived from the halo
        model and input halo occupation distribution.

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear galaxy power spectrum [Mpc/h]**3
        """
        return self.power_gm(k)

    def power_gg(self, k):
        """
        Non-Linear galaxy power spectrum derived from the halo
        model and input halo occupation distribution.

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear galaxy power spectrum [Mpc/h]**3
        """
        if not self._initialized_h_g:
            self._initialize_h_g()
        if not self._initialized_pp_gg:
            self._initialize_pp_gg()

        return self.power_mm(k)*self._h_g(k)*self._h_g(k) + self._pp_gg(k)

    def _initialize_h_g(self):
        h_g_array = numpy.zeros_like(self._ln_k_array)

        nu_min = self.mass.nu_min
        if (self.local_hod.first_moment_zero > -1 and
            self.local_hod.first_moment_zero >
            numpy.exp(self.mass.ln_mass_min)):
            nu_min = self.mass.nu(self.local_hod.first_moment_zero)
        for idx in xrange(self._ln_k_array.size):
            k = numpy.exp(self._ln_k_array[idx])
            
            h_g = integrate.romberg(
                self._h_g_integrand, numpy.log(nu_min),
                numpy.log(self.mass.nu_max), vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["halo_precision"],
                args=(self._ln_k_array[idx],),
                divmax=defaults.default_precision["divmax"])
            h_g_array[idx] = h_g

        ### We move the mass density normalization into the integrand here
        ### to prevent romberg having to integrate very small values.
        self._h_g_spline = InterpolatedUnivariateSpline(
            self._ln_k_array, h_g_array)
        self._initialized_h_g = True

    def _h_g_integrand(self, ln_nu, ln_k):
        nu = numpy.exp(ln_nu)
        mass = self.mass.mass(nu)

        return (nu*self._mass_window(mass, ln_k)*self.mass.f_nu(nu)*
                self.mass.bias_nu(nu)*self.y(ln_k, mass)*
                self.local_hod.first_moment(mass)/(
                mass*self.n_bar_over_rho_bar))

    def _mass_window(self, mass, ln_k):
        k = numpy.exp(ln_k)
        R = 2*self.virial_radius(mass)
        kR = k*R
        return ((kR*numpy.cos(kR) + kR*kR*kR*special.sici(kR)[1] +
                 (2 - kR*kR)*numpy.sin(kR))/(3.0*kR))
        
        
class HaloFit(Halo):
    """
    HALOFIT class with functional form of the non-linear power specrum from
    Smith2003 with new fit parameters from Takahashi2012. The HALOFIT method 
    derives only the non-linear power spectrum, other power spectra (gg and gm)
    are still from the halo model, however they utilize the HALOFIT non-linear
    power for the 2 halo term.
    
    Attributes:
         redshift: float redshift at which to compute the halo power spectra
         input_hod: HOD object from hod.py. Determines how galaxies populate 
             halos
         cosmo_single_epoch: SingleEpoch object from cosmology.py
         mass_func: MassFunction object from mass_function.py
         halo_dict: dictionary of floats defining halo properties. (see 
             defaults.py for details)
    """
    
    def __init__(self, redshift=0.0, input_hod=None, cosmo_single_epoch=None,
                 mass_func=None, halo_dict=None, **kws):
        Halo.__init__(self, redshift, input_hod, cosmo_single_epoch, mass_func,
                      halo_dict)
        self._initialize_halo_fit()
        self._initialized_sigma_spline = False
        
    def _initialize_halo_fit(self):
        self._f_1 = numpy.power(self.cosmo.omega_m(), -0.0307)
        self._f_2 = numpy.power(self.cosmo.omega_m(), -0.0585)
        self._f_3 = numpy.power(self.cosmo.omega_m(),  0.0743)
        self._omega_l = self.cosmo.omega_l()
        self._w = self.cosmo.w(self._redshift)
        
    def _initialize_sigma_spline(self):
        self._ln_R_array = numpy.linspace(
            numpy.log(0.1), numpy.log(10.0),
            defaults.default_precision["halo_npoints"])
        self._ln_sigma2_array = numpy.empty(
            defaults.default_precision["halo_npoints"])
        
        for idx, ln_R in enumerate(self._ln_R_array):
            R = numpy.exp(ln_R)
            sigma2 = integrate.romberg(
                self._sigma2_integrand, self._ln_k_min, self._ln_k_max,
                args=(R,), vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["halo_precision"],
                divmax=defaults.default_precision["divmax"])
            self._ln_sigma2_array[idx] = numpy.log(sigma2)
        
        ln_r_sigma2_spline = InterpolatedUnivariateSpline(
            self._ln_sigma2_array[::-1], self._ln_R_array[::-1])
        self._k_s = 1.0/numpy.exp(ln_r_sigma2_spline(0.0))
        ln_sigma2_r_spline = InterpolatedUnivariateSpline(
            self._ln_R_array, self._ln_sigma2_array,k=5)
        print "k_s:", self._k_s
        print "Derivatives:", ln_sigma2_r_spline.derivatives(
            numpy.log(1.0/self._k_s))
        (dev1, dev2) = ln_sigma2_r_spline.derivatives(
            numpy.log(1.0/self._k_s))[1:3]
        self._n_eff = -dev1 - 3.0
        self._C = -dev2
        
        self._a_n = numpy.power(10,
            1.5222 + 2.8553*self._n_eff + 2.3706*self._n_eff*self._n_eff +
            0.9903*self._n_eff*self._n_eff*self._n_eff +
            0.2250*self._n_eff*self._n_eff*self._n_eff*self._n_eff +
            -0.6038*self._C + 0.1749*self._omega_l*(1 + self._w))
        self._b_n = numpy.power(10,
            -0.5642 + 0.5864*self._n_eff + 0.5716*self._n_eff*self._n_eff +
            -1.5474*self._C + 0.2279*self._omega_l*(1 + self._w))
        self._c_n = numpy.power(10,
            0.3698 + 2.0404*self._n_eff + 0.8161*self._n_eff*self._n_eff +
            0.5869*self._C)
        self._gamma_n = 0.1971 - 0.0843*self._n_eff + 0.8460*self._C
        self._alpha_n = numpy.fabs(
            6.0835 + 1.3373*self._n_eff - 0.1959*self._n_eff*self._n_eff +
            -5.5274*self._C)
        self._beta_n = (
            2.0379 - 0.7354*self._n_eff + 0.3157*self._n_eff*self._n_eff +
            1.2490*self._n_eff*self._n_eff*self._n_eff +
            0.3980*self._n_eff*self._n_eff*self._n_eff*self._n_eff +
            -0.1682*self._C)
        self._mu_n = 0.0
        self._nu_n = numpy.power(10, 5.2105 + 3.6902*self._n_eff)
    
    def _sigma2_integrand(self, ln_k, R):
        k = numpy.exp(ln_k)
        return self.cosmo.delta_k(k)*numpy.exp(-k*k*R*R)
        
    def power_mm(self, k):
        """
        Non-Linear matter power spectrum derived from HALOFIT. This power
        spectrum should be used for correlations that depend only on dark matter
        (ie cosmo shear and magnification).

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear matter power spectrum [Mpc/h]**3
        """

        if not self._initialized_sigma_spline:
            self._initialize_sigma_spline()
        return 2.0*numpy.pi*numpy.pi/numpy.power(k, 3)*(
            self._delta2_Q(k) + self._delta2_H(k))
        
    def _delta2_Q(self, k):
        delta_k = self.cosmo.delta_k(k)
        return delta_k*(
            numpy.power(1 + delta_k, self._beta_n)/(1 + self._alpha_n*delta_k)*
            numpy.exp(-self._f(k)))
        
    def _f(self, k):
        y = k/self._k_s
        return y/4.0 + y*y/8.0
        
    def _delta2_H(self, k):
        y = k/self._k_s
        return self._delta2_prime_H(k)/(
            1 + self._mu_n/y + self._nu_n/(y*y))
        
    def _delta2_prime_H(self, y):
        return self._a_n*numpy.power(y, 3.0*self._f_1)/(
            1.0 + self._b_n*numpy.power(y, self._f_2) +
            numpy.power(self._c_n*self._f_3*y, 3.0 - self._gamma_n))
            
    def power_gm(self, k):
        """
        Non-Linear galaxy-matter cross power spectrum derived from the halo
        model and input halo occupation distribution.This power spectrum should
        be used for correlations that depend on the cross-correlation between
        galaxies and dark matter.
        (ie galaxy-galaxy shear and magnification).

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear galaxy-matter power spectrum [Mpc/h]**3
        """
        if not self._initialized_h_m:
            self._initialize_h_m()
        if not self._initialized_h_g:
            self._initialize_h_g()
        if not self._initialized_pp_gm:
            self._initialize_pp_gm()

        return self.power_mm(k)*self._h_g(k)*self._h_m(k) + self._pp_gm(k)

    def power_mg(self, k):
        """
        Non-Linear galaxy-matter cross power spectrum derived from the halo
        model and input halo occupation distribution. This power spectrum 
        should be used for correlations between galaxies and matter.
        themselves. (ie galaxy clustering/auto-correlations)

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear galaxy-matter power spectrum [Mpc/h]**3
        """
        return self.power_gm(k)

    def power_gg(self, k):
        """
        Non-Linear galaxy power spectrum derived from the halo
        model and input halo occupation distribution.

        Args:
            k [h/Mpc]: float array wave number
        Returns:
            float array non-linear galaxy power spectrum [Mpc/h]**3
        """
        if not self._initialized_h_g:
            self._initialize_h_g()
        if not self._initialized_pp_gg:
            self._initialize_pp_gg()

        return self.power_mm(k)*self._h_g(k)*self._h_g(k) + self._pp_gg(k)
        
    