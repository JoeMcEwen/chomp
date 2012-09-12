from copy import copy
import cosmology
import defaults
import kernel
import halo
import halo_trispectrum
import numpy
from scipy import special
from scipy import integrate
from scipy.interpolate import InterpolatedUnivariateSpline

"""Objects for computing covariance marix given an input survey are, theta
   limits, and binning.
"""

deg_to_rad = numpy.pi/180.0
rad_to_deg = 180.0/numpy.pi
deg2_to_strad = deg_to_rad*deg_to_rad
strad_to_deg2 = rad_to_deg*rad_to_deg

class Covariance(object):
    """
    Class to compute the covariance matrix between theta_a and thata_b
    given input kernel and halo trispectrum objects. This class can be used to
    estimate the covariance between different estimators as a function.

    Attributes:
        theta_min: minimum angular extent in radians
        theta_max: maximum angular extent in radians
        input_kernel: KernelTrispectrum object from kernel.py
        input_halo: HaloTrispectrum object from halo.py
        input_hod: HOD object from hod.py
        
        theta_array: array of theta values for computed correlation function
        wcovar_array: array of computed covariance values at theta_array values
    """

    def __init__(self, theta_min_deg, theta_max_deg,
                 bins_per_decade=5,
                 survey_area_deg2=4*numpy.pi*strad_to_deg2,
                 n_pairs=1e6*1e6, variance=1.0,
                 input_kernel_covariance=None,
                 input_halo=None,
                 input_halo_trispectrum=None, **kws):
        
        self.annular_bins = []
        unit_double = numpy.floor(numpy.log10(theta_min_deg))*bins_per_decade
        theta = numpy.power(10.0, unit_double/bins_per_decade)
        while theta < theta_max_deg:
            if theta >= theta_min_deg and theta < theta_max_deg:
                self.annular_bins.append(AnnulusBin(
                    theta, numpy.power(
                               10.0, (unit_double+1.0)/bins_per_decade)))
                unit_double += 1.0
                theta = numpy.power(10.0, unit_double/bins_per_decade)
                
        self.area = survey_area_deg2*deg2_to_strad
        self.n_pairs = n_pairs
        self.variance = variace

        self.kernel = input_kernel_covariance
        
        self._z_min_a = numpy.max([self.kernel.window_function_a1.z_min,
                                   self.kernel.window_function_a2.z_min])
        self._z_max_a = numpy.min([self.kernel.window_function_a1.z_max,
                                   self.kernel.window_function_a2.z_max])
        self._z_min_b = numpy.max([self.kernel.window_function_b1.z_min,
                                   self.kernel.window_function_b2.z_min])
        self._z_max_b = numpy.min([self.kernel.window_function_b1.z_max,
                                   self.kernel.window_function_b2.z_max])
        self._chi_min_a = self.kernel.cosmo.comoving_distance(self._z_min_a)
        if self._chi_min_a < 1e-8:
            self._chi_min_a = 1e-8
        self._chi_max_a = self.kernel.cosmo.comoving_distance(self._z_max_a)
        self._chi_min_b = self.kernel.cosmo.comoving_distance(self._z_min_b)
        if self._chi_min_b < 1e-8:
            self._chi_min_b = 1e-8
        self._chi_max_b = self.kernel.cosmo.comoving_distance(self._z_max_b)

        self.D_z_NG = self.kernel.cosmo.growth_factor(self.kernel.z_bar_NG)
        
        self.halo_a = input_halo
        self.halo_b = copy(input_halo)
        self.halo_tri = input_halo_trispectrum
        # self.halo.set_redshift(self.kernel.z_bar_G)
        # self.halo_tri.set_redshift(self.kernel.z_bar_NG)
        
        self._initialized_halo_splines = False
        self._ln_k_min = numpy.log(defaults.default_limits['k_min'])
        self._ln_k_max = numpy.log(defaults.default_limits['k_max'])
        self._ln_K_min = numpy.log(numpy.min(
            [defaults.default_limits['k_min']*self._chi_min_a,
             defaults.default_limits['k_min']*self._chi_min_b]))
        self._ln_K_max = numpy.log(numpy.max(
            [defaults.default_limits['k_max']*self._chi_max_a,
             defaults.default_limits['k_max']*self._chi_max_b]))
                                  
        self._ln_k_array = numpy.linspace(
            self._ln_k_min, self._ln_k_max,
            defaults.default_precision["kernel_npoints"])
        self._ln_K_array = numpy.linspace(
            self._ln_K_min, self._ln_K_max,
            defaults.default_precision["kernel_npoints"])
        
        self._int_G_norm = 1.0
        self._current_theta_a = -1.0
        self._current_theta_b = -1.0
        
        self._j0_limit = special.jn_zeros(
            0, defaults.default_precision["kernel_bessel_limit"])[-1]
               
    def _projected_halo_a(self, K):
        if not self._initialized_halo_splines:
            self._initialize_halo_splines()
        return numpy.exp(self._halo_a_spline(numpy.log(K)))
    
    def _projected_halo_b(self, K):
        if not self._initialized_halo_splines:
            self._initialize_halo_splines()
        return numpy.exp(self._halo_b_spline(numpy.log(K)))
    
    def get_covariance(self):
        out_covar = numpy.zeros((len(self.annular_bins),
                                 len(self.annular_bins)), 'float128')
        for idx1 in xrange(out_covar.shape[0]):
            for idx2 in xrange(idx1, out_covar.shape[1]):
                cov = self.covariance(self.annular_bins[idx1],
                                      self.annular_bins[idx2])
                if idx1 == idx2:
                    out_covar[idx1, idx2] = cov
                else:
                    out_covar[idx1, idx2] = cov
                    out_covar[idx2, idx1] = cov
                print (str(self.annular_bins[idx1].center)+' '+
                       str(self.annular_bins[idx2].center)+' '+
                       str(cov))
        return out_covar
        
    def covariance(self, annular_bin_a, annular_bin_b):
        cov_P = 0.0
        theta_a = annular_bin_a.center*deg_to_rad
        theta_b = annular_bin_b.center*deg_to_rad
        if annular_bin_a == annular_bin_b:
            cov_P = self.covariance_P(annular_bin_a.delta)
        return (cov_P + self.covariance_G(theta_a, theta_b) +
                self.covariance_NG(theta_a, theta_b))
    
    def covariance_P(self, delta):
        return self.area*self.variance/(
            self.n_pairs*2.0*numpy.pi*delta*deg_to_rad)
        
    def covariance_G(self, theta_a, theta_b):
        ### We normalize the integral so that romberg will have an easier time
        ### integrating it.
        if not self._initialized_halo_splines:
            self._initialize_halo_splines()
        ln_K_max = numpy.log(numpy.max([self._j0_limit/theta_a,
                                        self._j0_limit/theta_b]))
        if ln_K_max > self._ln_K_max:
            ln_K_max = self._ln_K_max
        elif ln_K_max <= self._ln_K_min:
            return 0.0
        
        norm = 1.0/self._covariance_G_integrand(0.0, 0.0, 0.0, 1.0)
        return integrate.romberg(
            self._covariance_G_integrand, self._ln_K_min, ln_K_max,
            args=(theta_a, theta_b, norm), vec_func=True, 
            tol=defaults.default_precision["global_precision"],
            rtol=defaults.default_precision["corr_precision"],
            divmax=defaults.default_precision["divmax"])/(
                norm*self._D_z_a*self._D_z_a*self._D_z_b*self._D_z_b*
                numpy.pi*self.area)
    
    def _covariance_G_integrand(self, ln_K, theta_a, theta_b, norm=1.0):
        K = numpy.exp(ln_K)
        dK = K
        return (dK*K*norm*self._projected_halo_a(K)*self._projected_halo_b(K)*
                special.j0(K*theta_a)*special.j0(K*theta_b))
        
    def _initialize_halo_splines(self):
        z_array_a = numpy.linspace(self._z_min_a, self._z_max_a,
                                   defaults.default_precision['kernel_npoints'],
                                   'float128')
        z_array_b = numpy.linspace(self._z_min_b, self._z_max_b,
                                   defaults.default_precision['kernel_npoints'],
                                   'float128')
        self._z_bar_G_a = z_array_a[numpy.argmax(
            self.kernel._kernel_G_a_integrand(
                self.kernel.cosmo.comoving_distance(z_array_a)))]
        self._z_bar_G_b = z_array_a[numpy.argmax(
            self.kernel._kernel_G_b_integrand(
                self.kernel.cosmo.comoving_distance(z_array_a)))]
        
        self.halo_a.set_redshift(self._z_bar_G_a)
        self.halo_b.set_redshift(self._z_bar_G_b)
        
        self._D_z_a = self.kernel.cosmo.growth_factor(self._z_bar_G_a)
        self._D_z_b = self.kernel.cosmo.growth_factor(self._z_bar_G_b)
        chi_peak_a = self.kernel.cosmo.comoving_distance(self._D_z_a)
        chi_peak_b = self.kernel.cosmo.comoving_distance(self._D_z_b)
        
        _halo_a_array = numpy.empty(self._ln_K_array.shape)
        _halo_b_array = numpy.empty(self._ln_K_array.shape)
        
        for idx, ln_K in enumerate(self._ln_K_array):
            norm = 1.0/self._halo_a_integrand(chi_peak_a, ln_K, norm=1.0)
            _halo_a_array[idx] = integrate.romberg(
                self._halo_a_integrand, self._chi_min_a, self._chi_max_a,
                args=(ln_K, norm), vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["corr_precision"],
                divmax=defaults.default_precision["divmax"])/norm
            norm = 1.0/self._halo_a_integrand(chi_peak_b, ln_K, norm=1.0)
            _halo_b_array[idx] = integrate.romberg(
                self._halo_b_integrand, self._chi_min_b, self._chi_max_b,
                args=(ln_K, norm), vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["corr_precision"],
                divmax=defaults.default_precision["divmax"])/norm
            
        self._halo_a_spline = InterpolatedUnivariateSpline(
            self._ln_K_array, numpy.log(_halo_a_array))
        self._halo_b_spline = InterpolatedUnivariateSpline(
            self._ln_K_array, numpy.log(_halo_b_array))
        
        self._initialized_halo_splines = True
    
    def _halo_a_integrand(self, chi, ln_K, norm=1.0):
        K = numpy.exp(ln_K)
        return (norm*self.halo_a.power_mm(K/chi)*
                self.kernel._kernel_G_a_integrand(chi))
    
    def _halo_b_integrand(self, chi, ln_K, norm=1.0):
        K = numpy.exp(ln_K)
        return (norm*self.halo_a.power_mm(K/chi)*
                self.kernel._kernel_G_b_integrand(chi))
        
    def covariance_NG(self, theta_a_rad, theta_b_rad):
        self._initialize_kb_spline(theta_a_rad, theta_b_rad)
        
        norm = 1.0/self._ka_integrand(0.0, 1.0)
        
        return integrate.romberg(
            self._ka_integrand, self._ln_k_min, self._ln_k_max, vec_func=True,
            args=(norm,),
            tol=defaults.default_precision["global_precision"],
            rtol=defaults.default_precision["corr_precision"],
            divmax=defaults.default_precision["divmax"])/(
                4.0*numpy.pi*numpy.pi*norm*self.area)
        
    def _ka_integrand(self, ln_ka, norm=1.0):
        dln_ka = 1.0
        ka = numpy.exp(ln_ka)
        dka = ka*dln_ka
        return dka*ka*(
            numpy.exp(self._kb_spline(ln_ka)) + self._kb_min - 1e-16)*norm
    
    def _initialize_kb_spline(self, theta_a, theta_b):
        if (self._current_theta_a == theta_a and
            self._current_theta_b == theta_b):
            return None
        
        _kb_int_array = numpy.empty(self._ln_k_array.shape, 'float128')
        
        for idx, ln_k in enumerate(self._ln_k_array):
            _kb_int_array[idx] = self._kb_integral(ln_k, theta_a, theta_b)
            
        self._kb_min = numpy.min(_kb_int_array)
        self._kb_spline = InterpolatedUnivariateSpline(
            self._ln_k_array, numpy.log(_kb_int_array - self._kb_min + 1e-16))
    
    def _kb_integral(self, ln_k, theta_a, theta_b):
        if type(ln_k) == numpy.ndarray:
            kb_int = numpy.empty(ln_k.shape)
            
            inv_norm = self._kb_integrand(0.0, ln_k, theta_a, 
                                          theta_b, 1.0)
            norm = 1.0
            if inv_norm > 1e-16 or inv_norm < -1e-16:
                norm = 1/inv_norm
            else:
                norm = 1e16
            for idx, ln_k in enumerate(ln_k):
                kb_int[idx] = integrate.romberg(
                    self._kb_integrand, self._ln_k_min, self._ln_k_max,
                    args=(ln_k, theta_a, theta_b, norm), vec_func=True,
                    tol=defaults.default_precision["global_precision"],
                    rtol=defaults.default_precision["corr_precision"],
                    divmax=defaults.default_precision["divmax"])/(
                        norm*self.D_z_NG*self.D_z_NG*self.D_z_NG*self.D_z_NG)
            return kb_int

        inv_norm = self._kb_integrand(0.0, ln_k, theta_a, 
                                          theta_b, 1.0)
        norm = 1.0
        if inv_norm > 1e-16 or inv_norm < -1e-16:
            norm = 1/inv_norm
        else:
            norm = 1e16
        return integrate.romberg(
           self._kb_integrand, self._ln_k_min, self._ln_k_max,
           args=(ln_k, theta_a, theta_b, norm), vec_func=True,
           tol=defaults.default_precision["global_precision"],
           rtol=defaults.default_precision["corr_precision"],
           divmax=defaults.default_precision["divmax"])/(
               norm*self.D_z_NG*self.D_z_NG*self.D_z_NG*self.D_z_NG)
    
    def _kb_integrand(self, ln_kb, ln_ka, theta_a, theta_b, norm=1.0):
        dln_kb = 1.0
        ka = numpy.exp(ln_ka)
        kb = numpy.exp(ln_kb)
        dkb = kb*dln_kb
        return (dkb*kb*norm*self.halo_tri.trispectrum_parallelogram(ka, kb)*
            self.kernel.kernel(numpy.log(ka*theta_a),
                               numpy.log(kb*theta_b))[0])
    
    
class CovarianceFourier(object):
    
    def __init__(self, l_min, l_max, input_kernel_covariance=None,
                 input_halo=None, input_halo_trispectrum=None, **kws):
        
        self._ln_l_min = numpy.log(l_min)
        self._ln_l_max = numpy.log(l_max)
        self._ln_l_array = numpy.linspace(
            self._ln_l_min, self._ln_l_max,
            defaults.default_precision["corr_npoints"])
        
        self.kernel = input_kernel_covariance
        
        self._z_min_a1a2 = numpy.max([self.kernel.window_function_a1.z_min,
                                      self.kernel.window_function_a2.z_min])
        self._z_min_b1b2 = numpy.max([self.kernel.window_function_b1.z_min,
                                      self.kernel.window_function_b2.z_min])
        self._z_min_a1b2 = numpy.max([self.kernel.window_function_a1.z_min,
                                      self.kernel.window_function_b2.z_min])
        self._z_min_b1a2 = numpy.max([self.kernel.window_function_b1.z_min,
                                      self.kernel.window_function_a2.z_min])
        
        self._z_max_a1a2 = numpy.min([self.kernel.window_function_a1.z_max,
                                      self.kernel.window_function_a2.z_max])
        self._z_max_b1b2 = numpy.min([self.kernel.window_function_b1.z_max,
                                      self.kernel.window_function_b2.z_max])
        self._z_max_a1b2 = numpy.min([self.kernel.window_function_a1.z_max,
                                      self.kernel.window_function_b2.z_max])
        self._z_max_b1a2 = numpy.min([self.kernel.window_function_b1.z_max,
                                      self.kernel.window_function_a2.z_max])
        
        self._z_array = numpy.linspace(
            numpy.min([self._z_min_a1a2, self._z_min_b1b2,
                       self._z_min_a1b2, self._z_min_b1a2]),
            numpy.max([self._z_max_a1a2, self._z_max_b1b2,
                       self._z_max_a1b2, self._z_max_b1a2]),
            defaults.default_precision['kernel_npoints'])
        
        self.window_a1 = self.kernel.window_function_a1.window_function
        self.window_a2 = self.kernel.window_function_a2.window_function
        self.window_b1 = self.kernel.window_function_b1.window_function
        self.window_b2 = self.kernel.window_function_b2.window_function
        
        self.halo_a1a2 = input_halo
        self.halo_b1b2 = copy(input_halo)
        self.halo_a1b2 = copy(input_halo)
        self.halo_b1a2 = copy(input_halo)
        self.halo_tri = input_halo_trispectrum
        
        self._initialized_pl = False
        
    def covariance(self, l_a, l_b):
        pass
        
    def covariance_G(self, l):
        if not self._initialized_pl:
            self._initialize_pl()
        return 1.0/(2.0*l + 1.0)*(self._pl_a1a2(l)*self._pl_b1b2(l)+
                self._pl_a1b2(l)*self._pl_b1a2(l))
                
    def _pl_a1a2(self, l):
        ln_l = numpy.log(l)
        return numpy.where(
            numpy.logical_and(ln_l >= self._ln_l_min, ln_l <= self._ln_l_max),
            numpy.exp(self._a1a2_spline(ln_l))/self._norm_G_a1a2, 0.0)
   
    def _pl_b1b2(self, l):
        ln_l = numpy.log(l)
        return numpy.where(
            numpy.logical_and(ln_l >= self._ln_l_min, ln_l <= self._ln_l_max),
            numpy.exp(self._b1b2_spline(ln_l))/self._norm_G_b1b2, 0.0)
            
    def _pl_a1b2(self, l):
        ln_l = numpy.log(l)
        return numpy.where(
            numpy.logical_and(ln_l >= self._ln_l_min, ln_l <= self._ln_l_max),
            numpy.exp(self._a1b2_spline(ln_l))/self._norm_G_a1b2, 0.0)
            
    def _pl_b1a2(self, l):
        ln_l = numpy.log(l)
        return numpy.where(
            numpy.logical_and(ln_l >= self._ln_l_min, ln_l <= self._ln_l_max),
            numpy.exp(self._b1a2_spline(ln_l))/self._norm_G_b1a2, 0.0)
            
    def _initialize_pl(self):
        self._z_bar_G_a1a2 = self._calculate_zbar(self.window_a1,
                                                  self.window_a2)
        self._z_bar_G_b1b2 = self._calculate_zbar(self.window_b1,
                                                  self.window_b2)
        self._z_bar_G_a1b2 = self._calculate_zbar(self.window_a1,
                                                  self.window_b2)
        self._z_bar_G_b1a2 = self._calculate_zbar(self.window_b1,
                                                  self.window_a2)
        
        self.halo_a1a2.set_redshift(self._z_bar_G_a1a2)
        self.halo_b1b2.set_redshift(self._z_bar_G_b1b2)
        self.halo_a1b2.set_redshift(self._z_bar_G_a1b2)
        self.halo_b1a2.set_redshift(self._z_bar_G_b1a2)
        chi_a1a2 = self.kernel.cosmo.comoving_distance(self._z_bar_G_a1a2)
        chi_b1b2 = self.kernel.cosmo.comoving_distance(self._z_bar_G_b1b2)
        chi_a1b2 = self.kernel.cosmo.comoving_distance(self._z_bar_G_a1b2)
        chi_b1a2 = self.kernel.cosmo.comoving_distance(self._z_bar_G_b1a2)
            
        chi_a1a2_min = self.kernel.cosmo.comoving_distance(self._z_min_a1a2)
        chi_b1b2_min = self.kernel.cosmo.comoving_distance(self._z_min_b1b2)
        chi_a1b2_min = self.kernel.cosmo.comoving_distance(self._z_min_a1b2)
        chi_b1a2_min = self.kernel.cosmo.comoving_distance(self._z_min_b1a2)
        
        chi_a1a2_max = self.kernel.cosmo.comoving_distance(self._z_max_a1a2)
        chi_b1b2_max = self.kernel.cosmo.comoving_distance(self._z_max_b1b2)
        chi_a1b2_max = self.kernel.cosmo.comoving_distance(self._z_max_a1b2)
        chi_b1a2_max = self.kernel.cosmo.comoving_distance(self._z_max_b1a2)
            
        self._norm_G_a1a2= 1.0/self._pl_integrand(chi_a1a2,
                                                  numpy.log(chi_a1a2),
                                                  self.halo_a1a2,
                                                  self.window_a1,
                                                  self.window_a2, 1.0)
        self._norm_G_b1b2= 1.0/self._pl_integrand(chi_b1b2,
                                                  numpy.log(chi_b1b2),
                                                  self.halo_b1b2,
                                                  self.window_a1,
                                                  self.window_a2, 1.0)
        self._norm_G_a1b2= 1.0/self._pl_integrand(chi_a1b2,
                                                  numpy.log(chi_a1b2),
                                                  self.halo_a1a2,
                                                  self.window_a1,
                                                  self.window_a2, 1.0)
        self._norm_G_b1a2= 1.0/self._pl_integrand(chi_b1a2,
                                                  numpy.log(chi_b1a2),
                                                  self.halo_b1a2,
                                                  self.window_a1,
                                                  self.window_a2, 1.0)
        
        _pl_a1a2 = numpy.empty(self._ln_l_array.shape)
        _pl_b1b2 = numpy.empty(self._ln_l_array.shape)
        _pl_a1b2 = numpy.empty(self._ln_l_array.shape)
        _pl_b1a2 = numpy.empty(self._ln_l_array.shape)
        for idx, ln_l in enumerate(self._ln_l_array):
            _pl_a1a2[idx] = integrate.romberg(
                self._pl_integrand, chi_a1a2_min, chi_a1a2_max,
                args=(ln_l, self.halo_a1a2, self.window_a1, self.window_a2,
                      self._norm_G_a1a2),
                vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["corr_precision"],
                divmax=defaults.default_precision["divmax"])
            _pl_b1b2[idx] = integrate.romberg(
                self._pl_integrand, chi_b1b2_min, chi_b1b2_max,
                args=(ln_l, self.halo_b1b2, self.window_b1, self.window_b2,
                      self._norm_G_b1b2),
                vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["corr_precision"],
                divmax=defaults.default_precision["divmax"])
            _pl_a1b2[idx] = integrate.romberg(
                self._pl_integrand, chi_a1b2_min, chi_a1b2_max,
                args=(ln_l, self.halo_a1b2, self.window_a1, self.window_b2,
                      self._norm_G_a1b2),
                vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["corr_precision"],
                divmax=defaults.default_precision["divmax"])
            _pl_b1a2[idx] = integrate.romberg(
                self._pl_integrand, chi_b1a2_min, chi_b1a2_max,
                args=(ln_l, self.halo_b1a2, self.window_b1, self.window_a2,
                      self._norm_G_b1a2),
                vec_func=True,
                tol=defaults.default_precision["global_precision"],
                rtol=defaults.default_precision["corr_precision"],
                divmax=defaults.default_precision["divmax"])
            
        print _pl_a1a2
                      
        self._a1a2_spline = InterpolatedUnivariateSpline(
            self._ln_l_array,
            numpy.log(_pl_a1a2/
                      self.kernel.cosmo.growth_factor(self._z_bar_G_a1a2)**2))
        self._b1b2_spline = InterpolatedUnivariateSpline(
            self._ln_l_array,
            numpy.log(_pl_b1b2/
                      self.kernel.cosmo.growth_factor(self._z_bar_G_b1b2)**2))
        self._a1b2_spline = InterpolatedUnivariateSpline(
            self._ln_l_array,
            numpy.log(_pl_a1b2/
                      self.kernel.cosmo.growth_factor(self._z_bar_G_a1b2)**2))
        self._b1a2_spline = InterpolatedUnivariateSpline(
            self._ln_l_array,
            numpy.log(_pl_b1a2/
                      self.kernel.cosmo.growth_factor(self._z_bar_G_b1a2)**2))
        
        self._initialized_pl = True      
        
    def _calculate_zbar(self, window1, window2):
        func = lambda chi: (window1(chi)*window2(chi)/(chi*chi)*
                            self.kernel.cosmo.growth_factor(
                                self.kernel.cosmo.redshift(chi))*
                            self.kernel.cosmo.growth_factor(
                                self.kernel.cosmo.redshift(chi)))
        print func(self.kernel.cosmo.comoving_distance(self._z_array))
        return self._z_array[numpy.argmax(
            func(self.kernel.cosmo.comoving_distance(self._z_array)))]
        
    def _pl_integrand(self, chi, ln_l, halo, window1, window2, norm):
        l = numpy.exp(ln_l)
        k = l/chi
        D_z = self.kernel.cosmo.growth_factor(
            self.kernel.cosmo.redshift(chi))
        return (norm*window1(chi)*window2(chi)*D_z*D_z/(chi*chi)*
                halo.power_mm(k))
        
class AnnulusBin(object):
    
    def __init__(self, inner, outer):
        self.inner = inner
        self.outer = outer
        self.center = numpy.power(10.0,0.5*(numpy.log10(inner)+
                                            numpy.log10(outer)))
        self.delta = outer - inner