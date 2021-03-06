# -*- coding: utf-8 -*-
"""
Created on Thu Apr  4 15:45:13 2019

Instead of simulate the whole image which is radiant symmetrical,
A line in the far field is simulated
The near field line simulation is converted from the far field line
through a Hankel transform 

Editor:
    Shihao Ran
    STIM Laboratory
"""
import time
import numpy as np
import scipy as sp
import scipy.special
import math
import matplotlib.pyplot as plt
from hankel import HankelTransform

#%%
# Calculate the sphere scattering coefficients
def coeff_b(l, k, n, a):
    jka = sp.special.spherical_jn(l, k * a)
    jka_p = sp.special.spherical_jn(l, k * a, derivative=True)
    jkna = sp.special.spherical_jn(l, k * n * a)
    jkna_p = sp.special.spherical_jn(l, k * n * a, derivative=True)

    yka = sp.special.spherical_yn(l, k * a)
    yka_p = sp.special.spherical_yn(l, k * a, derivative=True)

    hka = jka + yka * 1j
    hka_p = jka_p + yka_p * 1j

    bi = jka * jkna_p * n
    ci = jkna * jka_p
    di = jkna * hka_p
    ei = hka * jkna_p * n

    # return ai * (bi - ci) / (di - ei)
    return (bi - ci) / (di - ei)

#%%
class planewave():
    #implement all features of a plane wave
    #   k, E, frequency (or wavelength in a vacuum)--l
    #   try to enforce that E and k have to be orthogonal
    
    #initialization function that sets these parameters when a plane wave is created
    def __init__ (self, k, E):
        
        #self.phi = phi
        self.k = k/np.linalg.norm(k)                      
        self.E = E
        
        #force E and k to be orthogonal
        if ( np.linalg.norm(k) > 1e-15 and np.linalg.norm(E) >1e-15):
            s = np.cross(k, E)              #compute an orthogonal side vector
            s = s / np.linalg.norm(s)       #normalize it
            Edir = np.cross(s, k)              #compute new E vector which is orthogonal
            self.k = k
            self.E = Edir / np.linalg.norm(Edir) * np.linalg.norm(E)
    
    def __str__(self):
        return str(self.k) + "\n" + str(self.E)     #for verify field vectors use print command

    #function that renders the plane wave given a set of coordinates
    def evaluate(self, X, Y, Z):
        k_dot_r = self.k[0] * X + self.k[1] * Y + self.k[2] * Z     #phase term k*r
        ex = np.exp(1j * k_dot_r)       #E field equation  = E0 * exp (i * (k * r)) here we simply set amplitude as 1
        Ef = self.E.reshape((3, 1, 1)) * ex
        return Ef
    
#%%
def cal_Et_far_field(a, n, k, k_dir, res, fov, working_dis, scale_factor):
# calculate the scattering field through far field simulation
    
    # the maximal order
    l_max = math.ceil(2*np.pi * a / lambDa + 4 * (2 * np.pi * a / lambDa) ** (1/3) + 2)
    l = np.arange(0, l_max+1, 1)
    
    # calculate B coefficient
    B = coeff_b(l, k, n, a)
    
    # construct the evaluate plane
    
    # simulation resolution
    # in order to do fft and ifft, expand the image use padding
    simRes = int(res*(2*padding + 1))
    simFov = int(fov*(2*padding + 1))
    # halfgrid is the size of a half grid
    halfgrid = np.ceil(simFov/2)
    # range of x, y
    gx = np.linspace(-halfgrid, +halfgrid, simRes)
    gy = gx
    [x, y] = np.meshgrid(gx, gy)     
    # make it a plane at z = 0 (plus the working distance) on the Z axis
    z = np.zeros((simRes, simRes,)) + working_dis
    
    # initialize r vectors in the space
    rVecs = np.zeros((simRes, simRes, 3))
    # make x, y, z components
    rVecs[:,:,0] = x
    rVecs[:,:,1] = y
    rVecs[:,:,2] = z
    # compute the rvector relative to the sphere
    rVecs_ps = rVecs - ps
    
    # calculate the distance matrix
    rMag = np.sqrt(np.sum(rVecs_ps ** 2, 2))
    kMag = 2 * np.pi / lambDa
    # calculate k dot r
    kr = kMag * rMag
    
    # calculate the asymptotic form of hankel funtions
    hlkr_asym = np.zeros((kr.shape[0], kr.shape[1], l.shape[0]), dtype = np.complex128)
    for i in l:
        hlkr_asym[..., i] = np.exp(1j*(kr-i*math.pi/2))/(1j * kr)
    
    # calculate the legendre polynomial
    # get the frequency components
    fx = np.fft.fftfreq(simRes, simFov/simRes)
    fy = fx
    
    # create a meshgrid in the Fourier Domain
    [kx, ky] = np.meshgrid(fx, fy)
    # calculate the sum of kx ky components so we can calculate 
    # cos_theta in the Fourier Domain later
    kxky = kx ** 2 + ky ** 2
    # create a mask where the sum of kx^2 + ky^2 is 
    # bigger than 1 (where kz is not defined)
    mask = kxky > 1
    # mask out the sum
    kxky[mask] = 0
    # calculate cos theta in Fourier domain
    cos_theta = np.sqrt(1 - kxky)
    cos_theta[mask] = 0
    # calculate the Legendre Polynomial term
    pl_cos_theta = sp.special.eval_legendre(l, cos_theta[..., None])
    # mask out the light that is propagating outside of the objective
    pl_cos_theta[mask] = 0
    
    # calculate the prefix alpha term
    alpha = (2*l + 1) * 1j ** l
    # calculate the matrix besides B vector
    scatter_matrix = hlkr_asym * pl_cos_theta * alpha
    # calculate every order of the integration
    Sum = scatter_matrix * B
    # integrate through all the orders to get the farfield in the Fourier Domain
    E_scatter_fft = np.sum(Sum, axis = -1) * scale_factor
    
    # shift the Forier transform of the scatttering field for visualization
    E_scatter_fftshift = np.fft.fftshift(E_scatter_fft)
    
    # convert back to spatial domain
    E_scattering_b4_shift = np.fft.ifft2(E_scatter_fft)
    
    # shift the scattering field in the spacial domain for visualization
    E_scattering = np.fft.fftshift(E_scattering_b4_shift)
    
    Ei_obj = planewave(k_dir, E)
    Ei = Ei_obj.evaluate(x, y, np.zeros((simRes, simRes,)))
    E_incident = Ei[0, ...]
    Et = E_scattering + E_incident
    
    return Et, E_scattering, E_scatter_fftshift

def BPF(halfgrid, simRes, NA_in, NA_out):
    #create a bandpass filter
        #change coordinates into frequency domain
        
    df = 1/(halfgrid*2)
    
    iv, iu = np.meshgrid(np.arange(0, simRes, 1), np.arange(0, simRes, 1))
    
    u = np.zeros(iu.shape)
    v = np.zeros(iv.shape)
    
    #initialize the filter as All Pass
    BPF = np.ones(iv.shape)
    
    idex1, idex2 = np.where(iu <= simRes/2)
    u[idex1, idex2] = iu[idex1, idex2]
    
    idex1, idex2 = np.where(iu > simRes/2)
    u[idex1, idex2] = iu[idex1, idex2] - simRes +1
    
    u *= df
    
    idex1, idex2 = np.where(iv <= simRes/2)
    v[idex1, idex2] = iv[idex1, idex2]
    
    idex1, idex2 = np.where(iv > simRes/2)
    v[idex1, idex2] = iv[idex1, idex2] - simRes +1
    
    v *= df
    
    magf = np.sqrt(u ** 2 + v ** 2)
    
    #block lower frequency
    idex1, idex2 = np.where(magf < NA_in / lambDa)
    BPF[idex1, idex2] = 0
    #block higher frequency
    idex1, idex2 = np.where(magf > NA_out / lambDa)
    BPF[idex1, idex2] = 0
    
    return BPF

def new_bpf(simFov, simRes, NA_in, NA_out):
    # basically, a bandpass filter is just a circular mask
    # with inner and outer diamater specified by the 
    # in and out NA
    f_x = np.fft.fftfreq(simRes, simFov/simRes)
    
    fx, fy = np.meshgrid(f_x, f_x)
    
    fxfy = np.sqrt(fx ** 2 + fy ** 2)
    
    bpf_test = np.zeros((simRes, simRes))
    
    mask_out = fxfy <= NA_out
    mask_in = fxfy >= NA_in
    
    mask = np.logical_and(mask_out, mask_in)
    
    bpf_test[mask] = 1
    
    return bpf_test
    
def imgAtDetec(Etot, bpf):
    #2D fft to the total field
    Et_d = np.fft.fft2(np.fft.fftshift(Etot))
#    Et_return = np.fft.fft2(Etot)
#    Ef_d = np.fft.fft2(Ef)
    
    #apply bandpass filter to the fourier domain
    Et_d *= bpf
#    Ef_d *= bpf
    
    #invert FFT back to spatial domain
    Et_bpf = np.fft.fftshift(np.fft.ifft2(Et_d))
#    Ef_bpf = np.fft.ifft2(Ef_d)
    
    #initialize cropping
    cropsize = res
    startIdx = int(np.fix(simRes /2) - np.floor(cropsize/2))
    endIdx = int(startIdx + cropsize - 1)
    
    D_Et = np.zeros((cropsize, cropsize), dtype = np.complex128)
    D_Et = Et_bpf[startIdx:endIdx+1, startIdx:endIdx+1]
#    D_Ef = np.zeros((cropsize, cropsize), dtype = np.complex128)
#    D_Ef = Ef_bpf[startIdx:endIdx, startIdx:endIdx]

    return D_Et, Et_d

#%%
# set the size and resolution of both planes
fov = 16                    # field of view
res = 128                   # resolution
a = 1                       # radius of the spere
lambDa = 1                  # wavelength
n = 1.25 + 0.03j            # refractive index
k = 2 * math.pi / lambDa    # wavenumber
padding = 3                # padding
working_dis = int(10000 * (padding * 2 + 1))          # working distance
scale_factor = working_dis * 2 * math.pi * res/fov            # scale factor of the intensity
NA_in = 0.0
NA_out = 0.5

ps = [0, 0, 0]              # position of the sphere
k_dir = [0, 0, -1]          # propagation direction of the plane wave
E = [1, 0, 0]               # electric field vector

#%%
start = time.time()
E_t, E_scattering, E_scatter_fftshift = cal_Et_far_field(a, n, k, k_dir,
                                                         res, fov,
                                                         working_dis, scale_factor)

end = time.time()
print(end-start)
simRes = int(res * (2 * padding + 1))
simFov = int(fov * (2 * padding + 1))
halfgrid = np.ceil(simFov/2)
bpf = BPF(halfgrid, simRes, NA_in, NA_out)
bpf_new = new_bpf(simFov, simRes, NA_in, NA_out)

E_t_bandpass, Et_f = imgAtDetec(E_t, bpf_new)

fx_axis = np.fft.fftshift(np.fft.fftfreq(simRes, simFov/simRes))

##%%
#plt.figure()
#plt.subplot(141)
#plt.imshow(np.real(E_t), extent=[-simFov/2, simFov/2, -simFov/2, simFov/2])
#plt.title('Fourier Domain, Real')
#plt.colorbar()
##plt.axis('off')
#
#plt.subplot(142)
#plt.imshow(np.real(np.fft.fftshift(bpf_new)), extent = [fx_axis[0], fx_axis[-1], fx_axis[0], fx_axis[-1]])
#plt.title('Fourier Domain, Real')
#plt.colorbar()
#
#plt.subplot(143)
#plt.imshow(np.real(np.fft.fftshift(Et_f)), extent = [fx_axis[0], fx_axis[-1], fx_axis[0], fx_axis[-1]])
#plt.title('Total, Real')
#plt.colorbar()
##plt.axis('off')
#
#plt.subplot(144)
#plt.imshow(np.real(E_t_bandpass), extent=[-fov/2, fov/2, -fov/2, fov/2])
#plt.title('Filtered Image, Real')
#plt.colorbar()

#plt.tight_layout()

#%%
length = int(simRes/2)
center_idx = int(simRes/2)
E_near = np.fft.ifftshift(np.fft.fft2(np.fft.fftshift(E_scatter_fftshift)))
near_line_gt = E_near[center_idx, center_idx:center_idx+length]
far_line = E_scatter_fftshift[center_idx, center_idx:center_idx+length]
#
#plt.figure()
#plt.subplot(211)
#plt.title('Near Field 2-D Real')
#plt.imshow(np.real(E_near), extent=[-simFov/2, simFov/2, -simFov/2, simFov/2])
#plt.subplot(212)
#plt.title('Near Field 1-D Profile')
#plt.plot(np.real(near_line_gt), label='Real')
#plt.plot(np.imag(near_line_gt), label='Imaginary')
#plt.xlabel('Pixel Index')
#plt.ylabel('Intensity')
#plt.legend()

#%%
#x = np.linspace(-simFov/2, simFov/2, simRes)[int(simRes/2):]
#y_r = np.real(far_line)
#y_i = np.imag(far_line)
#
#from scipy.interpolate import InterpolatedUnivariateSpline as Spline
#
#f_r = Spline(x, y_r, k=1)
#f_i = Spline(x, y_i, k=1)
#xf = np.linspace(-simFov/2, simFov/2, simRes*20)[int(simRes*20/2):]
#
#plt.figure()
#plt.plot(x, y_r, marker='.', linestyle='none', alpha=0.7, color='blue', ms=3)
#plt.plot(xf, f_r(xf), color='cyan', alpha=0.5, label='Real')
#plt.plot(x, y_i, marker='.', linestyle='none', alpha=0.7, color='red', ms=3)
#plt.plot(xf, f_i(xf), color='orange', alpha=0.5, label='Imaginary')
#plt.title('Curve Fit')
#plt.legend()
#plt.show()

