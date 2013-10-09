import cosmology
import correlation
import defaults
import halo
import halo_trispectrum
import hod
import kernel
import mass_function
import perturbation_spectra
import numpy
import unittest

deg_to_rad = numpy.pi/180.0

### In order for the unittests to work correctly, these are the assumed
### precision values of the code.
defaults.default_precision = {
    "corr_npoints": 50,
    "corr_precision":1.48e-6,
    "cosmo_npoints": 50,
    "cosmo_precision": 1.48e-8,
    "dNdz_precision": 1.48e-8,
    "halo_npoints": 50,
    "halo_precision": 1.48e-5, ### This value is mostly due to integrations over
                               ### the HOD. If you are intrested in dark matter
                               ### only, this precision can be increased with
                               ### no major hit to speed.
    "halo_limit" : 100,
    "kernel_npoints": 50,
    "kernel_precision": 1.48e-6,
    "kernel_limit": 100, ### If the variable force_quad is set in the Kernel 
                         ### class this value sets the limit for the quad
                         ### integration
    "kernel_bessel_limit": 8, ### Defines how many zeros before cutting off
                              ### the Bessel function in kernel.py
    "mass_npoints": 50,
    "mass_precision": 1.48e-8,
    "window_npoints": 50,
    "window_precision": 1.48e-6,
    "global_precision": 1.48e-32, ### Since the code has large range of values
                                  ### from say 1e-10 to 1e10 don't want to use
                                  ### absolute tolerances, instead using 
                                  ### relative tolerances to define convergence
                                  ### of our integrands
    "divmax":20
    }

p_dict = {
    "corr":5,
    "cosmo":7,
    "dndz":7,
    "halo":4,
    "kernel":5,
    "mass":7,
    "window":5
    }

### Fix cosmology used in the module in case the user changes the default
c_dict = {
    "omega_m0": 0.3 - 4.15e-5/0.7**2, ### total matter desnity at z=0
    "omega_b0": 0.046, ### baryon density at z=0
    "omega_l0": 0.7, ### dark energy density at z=0
    "omega_r0": 4.15e-5/0.7**2, ### radiation density at z=0
    "cmb_temp": 2.726, ### temperature of the CMB in K at z=0
    "h"       : 0.7, ### Hubble's constant at z=0 normalized to 1/100 km/s/Mpc
    "sigma_8" : 0.8, ### over-density of matter at 8.0 Mpc/h
    "n_scalar": 0.960, ### large k slope of the power spectrum
    "w0"      : -1.0, ### dark energy equation of state at z=0
    "wa"      : 0.0 ### varying dark energy equation of state. At a=0 the 
                    ### value is w0 + wa.
    }

c_dict_2 = {
    "omega_m0": 1.0 - 4.15e-5/0.7**2,
    "omega_b0": 0.046,
    "omega_l0": 0.0,
    "omega_r0": 4.15e-5/0.7**2,
    "cmb_temp": 2.726,
    "h"       : 0.7,
    "sigma_8" : 0.8,
    "n_scalar": 0.960,
    "w0"      : -1.0,
    "wa"      : 0.0
    }

h_dict = {
    "stq": 0.3,
    "st_little_a": 0.707,
    "c0": 9.,
    "beta": -0.13,
    "alpha": -1., ### Halo mass profile slope. [NFW = -1]
    "delta_v": -1. ### over-density for defining. -1 means default behavior of
                   ### redshift dependent over-density defined in NFW97
    }

h_dict_2 = {
    "stq": 0.5,
    "st_little_a": 0.5,
    "c0": 5.,
    "beta": -0.2,
    "alpha": -1, ### Halo mass profile slope. [NFW = -1]
    "delta_v": 200.0
    }

hod_dict = {
    "log_M_min":12.14,
    "sigma":     0.15,
    "log_M_0":  12.14,
    "log_M_1p": 13.43,
    "alpha":      1.0
    }

hod_dict_2 = {
    "log_M_min":14.06,
    "sigma":     0.71,
    "log_M_0":  14.06,
    "log_M_1p": 14.80,
    "alpha":      1.0
    }


degToRad = numpy.pi/180.0

### All precision values below come from running python2.7.2 in MacOS 10.7.4
### on a 1.7 GHz Intel Core i5
class CosmologyTestSingleEpoch(unittest.TestCase):

    def setUp(self):
        self.cosmo = cosmology.SingleEpoch(redshift=0.0, cosmo_dict=c_dict)
        
    def test_single_epoch(self):
        self.assertTrue(self.cosmo._flat)
        self.assertEqual(self.cosmo._redshift, 0.0)
        self.assertEqual(self.cosmo._chi, 0.0)
        self.assertEqual(numpy.log(self.cosmo._growth), 0.0)
        self.assertAlmostEqual(self.cosmo.omega_m(), 0.3 - 4.15e-5/0.7**2,
                               p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo.omega_l(), 0.7, p_dict["cosmo"])
        self.assertEqual(self.cosmo.w(self.cosmo._redshift), -1.0)
        self.assertAlmostEqual(numpy.log(self.cosmo.delta_v()), 
                               5.84412388, p_dict["cosmo"])
        self.assertAlmostEqual(numpy.log(self.cosmo.delta_c()),
                               0.51601430, p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo.sigma_r(8.0), 0.8, p_dict["cosmo"])
        
    def test_set_redshift(self):
        self.cosmo.set_redshift(1.0)
        self.assertTrue(self.cosmo._flat)
        self.assertEqual(self.cosmo._redshift, 1.0)
        self.assertAlmostEqual(numpy.log(self.cosmo._chi), 
                               7.74621235, p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo._growth, 0.61184534, p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo.omega_m(), 0.77405957,
                               p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo.omega_l(), 0.22583113,
                               p_dict["cosmo"])
        self.assertEqual(self.cosmo.w(self.cosmo._redshift), -1.0)
        self.assertAlmostEqual(numpy.log(self.cosmo.delta_v()),
                               5.8139178, p_dict["cosmo"])
        self.assertAlmostEqual(numpy.log(self.cosmo.delta_c()),
                               0.52122912, p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo.sigma_r(8.0), 0.48947627,
                               p_dict["cosmo"])

    def test_set_cosmology(self):
        self.cosmo.set_cosmology(c_dict_2, 1.0)
        self.assertTrue(self.cosmo._flat)
        self.assertEqual(self.cosmo._redshift, 1.0)
        self.assertAlmostEqual(numpy.log(self.cosmo._chi),
                               7.47091187, p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo._growth, 0.50001210, p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo.omega_m(), 0.99995765,
                               p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo.omega_l(), 0.0, p_dict["cosmo"])
        self.assertEqual(self.cosmo.w(self.cosmo._redshift), -1.0)
        self.assertAlmostEqual(numpy.log(self.cosmo.delta_v()),
                               5.87492980, p_dict["cosmo"])
        self.assertAlmostEqual(numpy.log(self.cosmo.delta_c()),
                               0.52263747, p_dict["cosmo"])
        self.assertAlmostEqual(self.cosmo.sigma_r(8.0), 0.40000968,
                               p_dict["cosmo"])

    def test_linear_power(self):
        k_array = numpy.logspace(-3, 2, 4)
        lin_power = [8.18733648, 9.49322932, 2.32587979, -7.75033120]
        for idx, k in enumerate(k_array):
            self.assertAlmostEqual(numpy.log(self.cosmo.linear_power(k)),
                                   lin_power[idx], p_dict["cosmo"])
        
        
class CosmologyTestMultiEpoch(unittest.TestCase):
    
    def setUp(self):
        self.cosmo = cosmology.MultiEpoch(0.0, 5.0, cosmo_dict=c_dict)

    def test_multi_epoch(self):
        chi_list = [-33.27881676, 7.18696727, 7.74621236, 8.60212868] 
        growth_list = [1.0, 0.77321062, 0.61184534, 0.21356291]
        omega_m_list = [0.3 - 4.15e-5/0.7**2, 0.59110684,
                        0.77405957, 0.98926392]
        omega_l_list = [0.7, 0.40878186,
                        0.22583113,0.01068951]
        w_list = [-1.0, -1.0, -1.0, -1.0]
        delta_v_list = [5.84412389, 5.72815452, 5.81391783, 6.73154414]
        delta_c_list = [0.5160143, 0.77694983, 1.01250486, 2.06640216]
        sigma_8_list = [0.8, 0.61856849, 0.48947627, 0.17085033]
        for idx, z in enumerate([0.0, 0.5, 1.0, 5.0]):
            self.assertAlmostEqual(
                numpy.where(self.cosmo.comoving_distance(z) > 1e-16, 
                            numpy.log(self.cosmo.comoving_distance(z)), 0.0),
                chi_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(self.cosmo.growth_factor(z),
                                   growth_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(self.cosmo.omega_m(z),
                                   omega_m_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(self.cosmo.omega_l(z),
                                   omega_l_list[idx], p_dict["cosmo"])
            self.assertEqual(self.cosmo.epoch0.w(z), w_list[idx])
            self.assertAlmostEqual(numpy.log(self.cosmo.delta_v(z)), 
                                   delta_v_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(numpy.log(self.cosmo.delta_c(z)),
                                   delta_c_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(self.cosmo.sigma_r(8.0, z),
                                   sigma_8_list[idx], p_dict["cosmo"])

    def test_set_cosmology(self):
        chi_list = [0.0, 7.00333340, 7.47091200, 8.17419983] 
        growth_list = [1.0, 0.66667731, 0.50001201, 0.16667338]
        omega_m_list = [1.0 - 4.15e-5/0.7**2, 0.99994353,
                        0.99995765,  0.99998588]
        omega_l_list = [0.0, 0.0, 0.0, 0.0]
        w_list = [-1.0, -1.0, -1.0, -1.0]
        delta_v_list = [5.18183013,  5.58726375,
                        5.87493001, 6.97351045]
        delta_c_list = [0.52263724, 0.92808654, 1.21576064, 2.31435676]
        sigma_8_list = [0.8, 0.53334185, 0.40000961, 0.13333871]
        
        self.cosmo.set_cosmology(c_dict_2)
        for idx, z in enumerate([0.0, 0.5, 1.0, 5.0]):
            self.assertAlmostEqual(
                numpy.where(self.cosmo.comoving_distance(z) > 1e-16, 
                            numpy.log(self.cosmo.comoving_distance(z)), 0.0),
                chi_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(self.cosmo.growth_factor(z),
                                   growth_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(self.cosmo.omega_m(z),
                                   omega_m_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(self.cosmo.omega_l(z),
                                   omega_l_list[idx], p_dict["cosmo"])
            self.assertEqual(self.cosmo.epoch0.w(z), w_list[idx])
            self.assertAlmostEqual(numpy.log(self.cosmo.delta_v(z)), 
                                   delta_v_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(numpy.log(self.cosmo.delta_c(z)),
                                   delta_c_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(self.cosmo.sigma_r(8.0, z),
                                   sigma_8_list[idx], p_dict["cosmo"])


class MassFunctionTest(unittest.TestCase):
    
    def setUp(self):
        cosmo = cosmology.SingleEpoch(0.0, c_dict)
        self.mass = mass_function.MassFunction(cosmo_single_epoch=cosmo,
                                               halo_dict=h_dict)
        self.mass_array = numpy.logspace(9, 16, 4)
        
    def test_mass_function(self):
        nu_list = [-1.99747602, -0.82727011, 0.90140729, 3.74064051]
        f_mass_list = [0.42709020, -0.48530888, -2.33704722, -18.08214019]
        for idx, mass in enumerate(self.mass_array):
            if (mass < numpy.exp(self.mass.ln_mass_min) or 
                mass > numpy.exp(self.mass.ln_mass_max)):
                    continue
            self.assertAlmostEqual(numpy.log(self.mass.nu(mass)), nu_list[idx],
                                   p_dict["cosmo"])
            self.assertAlmostEqual(numpy.log(self.mass.f_m(mass)),
                                   f_mass_list[idx], p_dict["cosmo"])

    def test_set_cosmology(self):
        nu_list = [0.0, -2.28092057, -0.05730617, 3.69571049]
        f_mass_list = [0.0, 0.62102549, -1.19592034, -17.41912466]
        self.mass.set_cosmology(c_dict_2)
        for idx, mass in enumerate(self.mass_array):
            if (mass < numpy.exp(self.mass.ln_mass_min) or 
                mass > numpy.exp(self.mass.ln_mass_max)):
                    continue
            self.assertAlmostEqual(numpy.log(self.mass.nu(mass)), nu_list[idx],
                                   p_dict["cosmo"])
            self.assertAlmostEqual(numpy.log(self.mass.f_m(mass)),
                                   f_mass_list[idx], p_dict["cosmo"])

    def test_set_halo(self):
        nu_list = [-1.99747602, -0.82727011, 0.90140729, 3.74064051]
        f_mass_list = [0.55782135, -0.53564392, -2.40781796, -14.18822247]
        self.mass.set_halo(h_dict_2)
        for idx, mass in enumerate(self.mass_array):
            if (mass < numpy.exp(self.mass.ln_mass_min) or 
                mass > numpy.exp(self.mass.ln_mass_max)):
                    continue
            self.assertAlmostEqual(numpy.log(self.mass.nu(mass)), nu_list[idx],
                                   p_dict["cosmo"])
            self.assertAlmostEqual(numpy.log(self.mass.f_m(mass)),
                                   f_mass_list[idx], p_dict["cosmo"])
            
    def test_set_redshift(self):
        nu_list = [-1.36324583, -0.33629526, 1.13361010, 3.45202251]
        f_mass_list = [-0.05565187, -0.91258021, -2.71203571, -14.18084165]
        self.mass.set_redshift(1.0)
        for idx, mass in enumerate(self.mass_array):
            if (mass < numpy.exp(self.mass.ln_mass_min) or 
                mass > numpy.exp(self.mass.ln_mass_max)):
                    continue
            self.assertAlmostEqual(numpy.log(self.mass.nu(mass)), nu_list[idx],
                                   p_dict["cosmo"])
            self.assertAlmostEqual(numpy.log(self.mass.f_m(mass)),
                                   f_mass_list[idx], p_dict["cosmo"])
            
                        
class HODTest(unittest.TestCase):
    
    def setUp(self):
        self.zheng = hod.HODZheng(hod_dict)
        self.mass_array = numpy.logspace(9, 16, 4)
        self.first_moment_list = [0.0, 0.0, 2.6732276, 372.48394295]
        self.second_moment_list = [0.0, 0.0, 6.14614597, 138743.2877621]
        self.nth_moment_list = [0.0, 0.0, 11.83175124, 51678901.92217977]
        
    def test_hod(self):
        for idx, mass in enumerate(self.mass_array):
             self.assertAlmostEqual(self.zheng.first_moment(mass),
                                    self.first_moment_list[idx])
             self.assertAlmostEqual(self.zheng.second_moment(mass),
                                    self.second_moment_list[idx])
             self.assertAlmostEqual(self.zheng.nth_moment(mass, 3),
                                    self.nth_moment_list[idx])


class HaloTest(unittest.TestCase):
    
    def setUp(self):
        cosmo = cosmology.SingleEpoch(0.0, cosmo_dict=c_dict)
        zheng = hod.HODZheng(hod_dict)
        self.h = halo.Halo(input_hod=zheng, cosmo_single_epoch=cosmo)
        self.k_array = numpy.logspace(-3, 2, 4)
        
    def test_halo(self):
        power_mm_list = [8.34446,  9.53808,
                         5.59943, -2.80473]
        power_gm_list = [8.24115,  9.47902,
                         5.19533, -0.71614]
        power_gg_list = [8.15671,  9.42601,
                         4.59654, -0.49075]
        for idx, k in enumerate(self.k_array):
            self.assertAlmostEqual(numpy.log(self.h.power_mm(k)),
                                   power_mm_list[idx], p_dict["halo"])
            self.assertAlmostEqual(numpy.log(self.h.power_gm(k)),
                                   power_gm_list[idx], p_dict["halo"])
            self.assertAlmostEqual(numpy.log(self.h.power_gg(k)),
                                   power_gg_list[idx], p_dict["halo"])
            
    def test_set_cosmology(self):
        linear_power_list = [5.16650870,  8.11613036,
                             3.69335247, -5.84391743]
        power_mm_list = [6.61709,  8.27371,
                         5.68236, -3.03705]
        power_gm_list = [5.91437,  7.94417,
                         4.95208, -1.46860]
        power_gg_list = [5.28356,  7.64378,
                         4.21950, -1.35347]
        self.h.set_cosmology(c_dict_2)
        for idx, k in enumerate(self.k_array):
            self.assertAlmostEqual(numpy.log(self.h.linear_power(k)),
                                   linear_power_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(numpy.log(self.h.power_mm(k)),
                                   power_mm_list[idx], p_dict["halo"])
            self.assertAlmostEqual(numpy.log(self.h.power_gm(k)),
                                   power_gm_list[idx], p_dict["halo"])
            self.assertAlmostEqual(numpy.log(self.h.power_gg(k)),
                                   power_gg_list[idx], p_dict["halo"])

    def test_set_halo(self):
        power_mm_list = [8.41964,  9.5614,
                         5.76978, -2.86396]
        power_gm_list = [8.27334,  9.47549,
                         5.37421, -0.73567]
        power_gg_list = [8.15326,  9.39862,
                         4.82581, -0.43823]
        self.h.set_halo(h_dict_2)
        for idx, k in enumerate(self.k_array):
            self.assertAlmostEqual(numpy.log(self.h.power_mm(k)),
                                   power_mm_list[idx], p_dict["halo"])
            self.assertAlmostEqual(numpy.log(self.h.power_gm(k)),
                                   power_gm_list[idx], p_dict["halo"])
            self.assertAlmostEqual(numpy.log(self.h.power_gg(k)),
                                   power_gg_list[idx], p_dict["halo"])

    def test_set_hod(self):
        power_gm_list = [8.84246,  9.98600,
                         6.68634,  1.20497]
        power_gg_list = [9.17274, 10.38198,
                         6.26546, -0.14734]
        self.h.set_hod(hod_dict_2)
        for idx, k in enumerate(self.k_array):
            self.assertAlmostEqual(numpy.log(self.h.power_gm(k)),
                                   power_gm_list[idx], p_dict["halo"])
            self.assertAlmostEqual(numpy.log(self.h.power_gg(k)),
                                   power_gg_list[idx], p_dict["halo"])
            
    def test_set_redshift(self):
        linear_power_list = [7.20478501, 8.51067786,
                             1.34332833, -8.73288266]
        power_mm_list = [7.25080,  8.52330,
                         3.82800, -4.41358]
        power_gm_list = [7.32677,  8.61186,
                         3.54628, -2.45831]
        power_gg_list = [7.40755,  8.70179,
                         3.16101, -2.07693]
        self.h.set_redshift(1.0)
        for idx, k in enumerate(self.k_array):
            self.assertAlmostEqual(numpy.log(self.h.linear_power(k)),
                                   linear_power_list[idx], p_dict["cosmo"])
            self.assertAlmostEqual(numpy.log(self.h.power_mm(k)),
                                   power_mm_list[idx], p_dict["halo"])
            self.assertAlmostEqual(numpy.log(self.h.power_gm(k)),
                                   power_gm_list[idx], p_dict["halo"])
            self.assertAlmostEqual(numpy.log(self.h.power_gg(k)),
                                   power_gg_list[idx], p_dict["halo"])

### Commented out currently as it is a future feature not yet mature.
# class HaloTriSpectrumTest(unittest.TestCase):
#    
#     def setUp(self):
#        cosmo = cosmology.SingleEpoch(0.0, cosmo_dict=c_dict)
#         mass = mass_function.MassFunctionSecondOrder(cosmo_single_epoch=cosmo,
#                                                     halo_dict=h_dict)
#         pert = perturbation_spectra.PerturbationTheory(
#            cosmo_single_epoch=cosmo)
#         self.h = halo_trispectrum.HaloTrispectrum(
#             redshift=0.0, single_epoch_cosmo=cosmo,
#             mass_func_second=mass, perturbation=pert, halo_dict=h_dict)
#         self.k_array = numpy.logspace(-3, 2, 4)
#         
#     def test_trispectrum(self):
#         for idx, k in enumerate(self.k_array):
#             self.assertGreater(
#                 self.h.trispectrum_parallelogram(k, k, 0.0), 0.0)


class dNdzTest(unittest.TestCase):

    def setUp(self):
        self.lens_dist = kernel.dNdzMagLim(z_min=0.0, z_max=2.0, 
                                           a=2, z0=0.3, b=2)
        self.source_dist = kernel.dNdzGaussian(z_min=0.0, z_max=2.0,
                                               z0=1.0, sigma_z=0.2)
        self.z_array = numpy.linspace(0.0, 2.0, 4)
        self.lens_dist_list = [0.0, 0.00318532, 0.0, 0.0]
        self.source_dist_list = [3.72665317e-06, 0.24935220, 
                                 0.24935220, 3.72665317e-06]

    def test_redshift_dist(self):
        for idx, z in enumerate(self.z_array):
             self.assertAlmostEqual(self.lens_dist.dndz(z),
                                    self.lens_dist_list[idx])
             self.assertAlmostEqual(self.source_dist.dndz(z),
                                    self.source_dist_list[idx])


class WindowFunctionTest(unittest.TestCase):

    def setUp(self):
        lens_dist = kernel.dNdzMagLim(z_min=0.0, z_max=2.0, 
                                           a=1, z0=0.3, b=1)
        source_dist = kernel.dNdzGaussian(z_min=0.0, z_max=2.0,
                                               z0=1.0, sigma_z=0.2)
        cosmo = cosmology.MultiEpoch(0.0, 5.0, cosmo_dict=c_dict)
        self.lens_window = kernel.WindowFunctionGalaxy(
            lens_dist, cosmo_multi_epoch=cosmo)
        self.source_window = kernel.WindowFunctionConvergence(
            source_dist, cosmo_multi_epoch=cosmo)
        self.z_array = numpy.linspace(0.0, 2.0, 4)
    
    def test_window_function(self):
        lens_window_list = [0.0, -13.999860, -13.307302, -12.902425]
        source_window_list = [0.0, -17.215741, -16.522670, -16.117281]
        for idx, z in enumerate(self.z_array):
            self.assertAlmostEqual(
                numpy.where(self.lens_window.window_function(z) > 1e-16,
                            numpy.log(self.lens_window.window_function(z)),
                            0.0), lens_window_list[idx], p_dict["window"])
            self.assertAlmostEqual(
                numpy.where(self.source_window.window_function(z) > 0.0,
                            numpy.log(self.source_window.window_function(z)),
                            0.0), source_window_list[idx], p_dict["window"])

    def test_set_cosmology(self):
        lens_window_list = [0.0, -13.999269, -13.306364, -12.901141]
        source_window_list = [0.0, -16.011668, -15.318688, -14.913390]
        
        cosmo = cosmology.MultiEpoch(0.0, 5.0, c_dict_2)
        self.lens_window.set_cosmology_object(cosmo)
        self.source_window.set_cosmology_object(cosmo)
        for idx, z in enumerate(self.z_array):
            self.assertAlmostEqual(
                numpy.where(self.lens_window.window_function(z) > 0.0,
                            numpy.log(self.lens_window.window_function(z)),
                            0.0), lens_window_list[idx], p_dict["window"])
            self.assertAlmostEqual(
                numpy.where(self.source_window.window_function(z) > 1e-32,
                            numpy.log(self.source_window.window_function(z)),
                            0.0), source_window_list[idx], p_dict["window"])


class KenrelTest(unittest.TestCase):

    def setUp(self):
        cosmo = cosmology.MultiEpoch(0.0, 5.0, cosmo_dict=c_dict)
        lens_dist = kernel.dNdzMagLim(z_min=0.0, z_max=2.0, 
                                      a=2, z0=0.3, b=2)
        source_dist = kernel.dNdzGaussian(z_min=0.0, z_max=2.0,
                                          z0=1.0, sigma_z=0.2)
        lens_window = kernel.WindowFunctionGalaxy(
            lens_dist, cosmo_multi_epoch=cosmo)
        source_window = kernel.WindowFunctionConvergence(
            source_dist, cosmo_multi_epoch=cosmo)
        self.kern = kernel.Kernel(0.001*0.001*degToRad, 1.0*100.0*degToRad,
                               window_function_a=lens_window,
                               window_function_b=source_window,
                               cosmo_multi_epoch=cosmo)
        self.ln_ktheta_array = numpy.linspace(-15, -1, 4)
        
    def test_kernel(self):
        k_list = [-10.688826, -10.689089,
                  -12.737842, -24.658868]
        for idx, ln_ktheta in enumerate(self.ln_ktheta_array):
            kern = numpy.abs(self.kern.kernel(ln_ktheta))
            self.assertAlmostEqual(
                numpy.where(kern > 0.0, numpy.log(kern), 0.0),
                k_list[idx], p_dict["kernel"])

    def test_set_cosmology(self):
        self.kern.set_cosmology(c_dict_2)
        k_list = [ -9.945842,  -9.946020,
                  -12.966945, -23.425243]
        for idx, ln_ktheta in enumerate(self.ln_ktheta_array):
            kern = numpy.abs(self.kern.kernel(ln_ktheta))
            self.assertAlmostEqual(
                numpy.where(kern > 0.0, numpy.log(kern), 0.0),
                k_list[idx], p_dict["kernel"])
            

class CorrelationTest(unittest.TestCase):
    
    def setUp(self):
        cosmo_multi = cosmology.MultiEpoch(0.0, 5.0, cosmo_dict=c_dict)
        lens_dist = kernel.dNdzMagLim(z_min=0.0, z_max=2.0, 
                                      a=2, z0=0.3, b=2)
        source_dist = kernel.dNdzGaussian(z_min=0.0, z_max=2.0,
                                          z0=1.0, sigma_z=0.2)
        lens_window = kernel.WindowFunctionGalaxy(
            lens_dist, cosmo_multi_epoch=cosmo_multi)
        source_window = kernel.WindowFunctionConvergence(
            source_dist, cosmo_multi_epoch=cosmo_multi)
        kern = kernel.Kernel(0.001*0.001*deg_to_rad, 1.0*100.0*deg_to_rad,
                             window_function_a=lens_window,
                             window_function_b=source_window,
                             cosmo_multi_epoch=cosmo_multi)
        
        zheng = hod.HODZheng(hod_dict)
        cosmo_single = cosmology.SingleEpoch(0.0, cosmo_dict=c_dict)
        h = halo.Halo(input_hod=zheng, cosmo_single_epoch=cosmo_single)
        self.corr = correlation.Correlation(0.001, 1.0,
                                            input_kernel=kern,
                                            input_halo=h,
                                            power_spec='power_mm')
        self.theta_array = numpy.logspace(-3, 0, 4)*deg_to_rad
        
    def test_correlation(self):
        corr_list = [-4.109842, -4.722583, -6.906498, -9.032731]
        for idx, theta in enumerate(self.theta_array):
            self.assertAlmostEqual(
                numpy.log(self.corr.correlation(theta)),
                corr_list[idx], p_dict["corr"])
            
    def test_set_cosmology(self):
        self.corr.set_cosmology(c_dict_2)
        corr_list = [-2.905774, -3.493072, -5.831428, -10.676284]
        for idx, theta in enumerate(self.theta_array):
            self.assertAlmostEqual(
                numpy.log(self.corr.correlation(theta)),
                corr_list[idx], p_dict["corr"])
            
    def test_set_hod(self):
        self.corr.set_hod(hod_dict_2)
        self.corr.set_power_spectrum('power_gm')
        corr_list = [-1.844441, -3.464648, -6.578803, -8.716385]
        for idx, theta in enumerate(self.theta_array):
            self.assertAlmostEqual(
                numpy.log(self.corr.correlation(theta)),
                corr_list[idx], p_dict["corr"])

    def test_set_redshift(self):
        self.corr.set_redshift(0.5)
        corr_list = [-4.207454, -4.824261, -6.987484, -9.014560]
        for idx, theta in enumerate(self.theta_array):
            self.assertAlmostEqual(
                numpy.log(self.corr.correlation(theta)),
                corr_list[idx], p_dict["corr"])
            
            
if __name__ == "__main__":
    print "*******************************"
    print "*                             *"
    print "*      CHOMP Unit Test        *"
    print "*                             *"
    print "*******************************"
    unittest.main()
    
