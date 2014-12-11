
################################################################################
#
# TRIQS: a Toolbox for Research in Interacting Quantum Systems
#
# Copyright (C) 2011 by M. Aichhorn, L. Pourovskii, V. Vildosola
#
# TRIQS is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# TRIQS is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# TRIQS. If not, see <http://www.gnu.org/licenses/>.
#
################################################################################

from types import *
import numpy
from pytriqs.gf.local import *
import pytriqs.utility.mpi as mpi
from symmetry import *
from sumk_dft import SumkDFT

class SumkDFTTools(SumkDFT):
    """Extends the SumkDFT class with some tools for analysing the data."""


    def __init__(self, hdf_file, h_field = 0.0, use_dft_blocks = False, dft_data = 'dft_input', symmcorr_data = 'dft_symmcorr_input',
                 parproj_data = 'dft_parproj_input', symmpar_data = 'dft_symmpar_input', bands_data = 'dft_bands_input', 
                 transp_data = 'dft_transp_input'):

        #self.G_latt_w = None # DEBUG -- remove later
        SumkDFT.__init__(self, hdf_file=hdf_file, h_field=h_field, use_dft_blocks=use_dft_blocks,
                          dft_data=dft_data, symmcorr_data=symmcorr_data, parproj_data=parproj_data, 
                          symmpar_data=symmpar_data, bands_data=bands_data, transp_data=transp_data)


    def downfold_pc(self,ik,ir,ish,bname,gf_to_downfold,gf_inp):
        """Downfolding a block of the Greens function"""

        gf_downfolded = gf_inp.copy()
        isp = self.spin_names_to_ind[self.SO][bname]       # get spin index for proj. matrices
        dim = self.shells[ish]['dim']
        n_orb = self.n_orbitals[ik,isp]
        L=self.proj_mat_pc[ik,isp,ish,ir,0:dim,0:n_orb]
        R=self.proj_mat_pc[ik,isp,ish,ir,0:dim,0:n_orb].conjugate().transpose()
        gf_downfolded.from_L_G_R(L,gf_to_downfold,R)

        return gf_downfolded


    def rotloc_all(self,ish,gf_to_rotate,direction):
        """Local <-> Global rotation of a GF block.
           direction: 'toLocal' / 'toGlobal' """

        assert (direction == 'toLocal' or direction == 'toGlobal'),"rotloc_all: Give direction 'toLocal' or 'toGlobal'."


        gf_rotated = gf_to_rotate.copy()
        if direction == 'toGlobal':
            if (self.rot_mat_all_time_inv[ish] == 1) and self.SO:
                gf_rotated << gf_rotated.transpose()
                gf_rotated.from_L_G_R(self.rot_mat_all[ish].conjugate(),gf_rotated,self.rot_mat_all[ish].transpose())
            else:
                gf_rotated.from_L_G_R(self.rot_mat_all[ish],gf_rotated,self.rot_mat_all[ish].conjugate().transpose())

        elif direction == 'toLocal':
            if (self.rot_mat_all_time_inv[ish] == 1) and self.SO:
                gf_rotated << gf_rotated.transpose()
                gf_rotated.from_L_G_R(self.rot_mat_all[ish].transpose(),gf_rotated,self.rot_mat_all[ish].conjugate())
            else:
                gf_rotated.from_L_G_R(self.rot_mat_all[ish].conjugate().transpose(),gf_rotated,self.rot_mat_all[ish])


        return gf_rotated


    def check_input_dos(self, om_min, om_max, n_om, beta=10, broadening=0.01):


        delta_om = (om_max-om_min)/(n_om-1)
        om_mesh = numpy.zeros([n_om],numpy.float_)
        for i in range(n_om): om_mesh[i] = om_min + delta_om * i

        DOS = {}
        for sp in self.spin_block_names[self.SO]:
            DOS[sp] = numpy.zeros([n_om],numpy.float_)

        DOSproj     = [ {} for ish in range(self.n_inequiv_shells) ]
        DOSproj_orb = [ {} for ish in range(self.n_inequiv_shells) ]
        for ish in range(self.n_inequiv_shells):
            for sp in self.spin_block_names[self.corr_shells[self.inequiv_to_corr[ish]]['SO']]:
                dim = self.corr_shells[self.inequiv_to_corr[ish]]['dim']
                DOSproj[ish][sp] = numpy.zeros([n_om],numpy.float_)
                DOSproj_orb[ish][sp] = numpy.zeros([n_om,dim,dim],numpy.float_)

        # init:
        Gloc = []
        for icrsh in range(self.n_corr_shells):
            spn = self.spin_block_names[self.corr_shells[icrsh]['SO']]
            glist = lambda : [ GfReFreq(indices = inner, window = (om_min,om_max), n_points = n_om) for block,inner in self.gf_struct_sumk[icrsh]]
            Gloc.append(BlockGf(name_list = spn, block_list = glist(),make_copies=False))
        for icrsh in range(self.n_corr_shells): Gloc[icrsh].zero()                        # initialize to zero

        for ik in range(self.n_k):

            G_latt_w=self.lattice_gf(ik=ik,mu=self.chemical_potential,iw_or_w="w",broadening=broadening,mesh=(om_min,om_max,n_om),with_Sigma=False)
            G_latt_w *= self.bz_weights[ik]

            # non-projected DOS
            for iom in range(n_om):
                for bname,gf in G_latt_w:
                    asd = gf.data[iom,:,:].imag.trace()/(-3.1415926535)
                    DOS[bname][iom] += asd

            for icrsh in range(self.n_corr_shells):
                tmp = Gloc[icrsh].copy()
                for bname,gf in tmp: tmp[bname] << self.downfold(ik,icrsh,bname,G_latt_w[bname],gf) # downfolding G
                Gloc[icrsh] += tmp



        if self.symm_op != 0: Gloc = self.symmcorr.symmetrize(Gloc)

        if self.use_rotations:
            for icrsh in range(self.n_corr_shells):
                for bname,gf in Gloc[icrsh]: Gloc[icrsh][bname] << self.rotloc(icrsh,gf,direction='toLocal')

        # Gloc can now also be used to look at orbitally resolved quantities
        for ish in range(self.n_inequiv_shells):
            for bname,gf in Gloc[self.inequiv_to_corr[ish]]: # loop over spins
                for iom in range(n_om): DOSproj[ish][bname][iom] += gf.data[iom,:,:].imag.trace()/(-3.1415926535)

                DOSproj_orb[ish][bname][:,:,:] += gf.data[:,:,:].imag/(-3.1415926535)

        # output:
        if mpi.is_master_node():
            for sp in self.spin_block_names[self.SO]:
                f=open('DOS%s.dat'%sp, 'w')
                for i in range(n_om): f.write("%s    %s\n"%(om_mesh[i],DOS[sp][i]))
                f.close()

                for ish in range(self.n_inequiv_shells):
                    f=open('DOS%s_proj%s.dat'%(sp,ish),'w')
                    for i in range(n_om): f.write("%s    %s\n"%(om_mesh[i],DOSproj[ish][sp][i]))
                    f.close()

                    for i in range(self.corr_shells[self.inequiv_to_corr[ish]]['dim']):
                        for j in range(i,self.corr_shells[self.inequiv_to_corr[ish]]['dim']):
                            Fname = 'DOS'+sp+'_proj'+str(ish)+'_'+str(i)+'_'+str(j)+'.dat'
                            f=open(Fname,'w')
                            for iom in range(n_om): f.write("%s    %s\n"%(om_mesh[iom],DOSproj_orb[ish][sp][iom,i,j]))
                            f.close()




    def read_parproj_input_from_hdf(self):
        """
        Reads the data for the partial projectors from the HDF file
        """

        things_to_read = ['dens_mat_below','n_parproj','proj_mat_pc','rot_mat_all','rot_mat_all_time_inv']
        value_read = self.read_input_from_hdf(subgrp=self.parproj_data,things_to_read = things_to_read)
        return value_read



    def dos_partial(self,broadening=0.01):
        """calculates the orbitally-resolved DOS"""

        assert hasattr(self,"Sigma_imp_w"), "dos_partial: Set Sigma_imp_w first."

        value_read = self.read_parproj_input_from_hdf()
        if not value_read: return value_read
        if self.symm_op: self.symmpar = Symmetry(self.hdf_file,subgroup=self.symmpar_data)

        mu = self.chemical_potential

        gf_struct_proj = [ [ (sp, range(self.shells[i]['dim'])) for sp in self.spin_block_names[self.SO] ]  for i in range(self.n_shells) ]
        Gproj = [BlockGf(name_block_generator = [ (block,GfReFreq(indices = inner, mesh = self.Sigma_imp_w[0].mesh)) 
                               for block,inner in gf_struct_proj[ish] ], make_copies = False ) for ish in range(self.n_shells)]
        for ish in range(self.n_shells): Gproj[ish].zero()

        mesh = [x.real for x in self.Sigma_imp_w[0].mesh]
        n_om = len(mesh)

        DOS = {}
        for sp in self.spin_block_names[self.SO]:
            DOS[sp] = numpy.zeros([n_om],numpy.float_)

        DOSproj     = [ {} for ish in range(self.n_shells) ]
        DOSproj_orb = [ {} for ish in range(self.n_shells) ]
        for ish in range(self.n_shells):
            for sp in self.spin_block_names[self.SO]:
                dim = self.shells[ish]['dim']
                DOSproj[ish][sp] = numpy.zeros([n_om],numpy.float_)
                DOSproj_orb[ish][sp] = numpy.zeros([n_om,dim,dim],numpy.float_)

        ikarray=numpy.array(range(self.n_k))

        for ik in mpi.slice_array(ikarray):

            G_latt_w = self.lattice_gf(ik=ik,mu=mu,iw_or_w="w",broadening=broadening)
            G_latt_w *= self.bz_weights[ik]

            # non-projected DOS
            for iom in range(n_om):
                for bname,gf in G_latt_w: DOS[bname][iom] += gf.data[iom,:,:].imag.trace()/(-3.1415926535)

            #projected DOS:
            for ish in range(self.n_shells):
                tmp = Gproj[ish].copy()
                for ir in range(self.n_parproj[ish]):
                    for bname,gf in tmp: tmp[bname] << self.downfold_pc(ik,ir,ish,bname,G_latt_w[bname],gf)
                    Gproj[ish] += tmp

        # collect data from mpi:
        for bname in DOS:
            DOS[bname] = mpi.all_reduce(mpi.world, DOS[bname], lambda x,y : x+y)
        for ish in range(self.n_shells):
            Gproj[ish] << mpi.all_reduce(mpi.world, Gproj[ish], lambda x,y : x+y)
        mpi.barrier()

        if self.symm_op != 0: Gproj = self.symmpar.symmetrize(Gproj)

        # rotation to local coord. system:
        if self.use_rotations:
            for ish in range(self.n_shells):
                for bname,gf in Gproj[ish]: Gproj[ish][bname] << self.rotloc_all(ish,gf,direction='toLocal')

        for ish in range(self.n_shells):
            for bname,gf in Gproj[ish]:
                for iom in range(n_om): DOSproj[ish][bname][iom] += gf.data[iom,:,:].imag.trace()/(-3.1415926535)
                DOSproj_orb[ish][bname][:,:,:] += gf.data[:,:,:].imag / (-3.1415926535)


        if mpi.is_master_node():
            # output to files
            for sp in self.spin_block_names[self.SO]:
                f=open('./DOScorr%s.dat'%sp, 'w')
                for i in range(n_om): f.write("%s    %s\n"%(mesh[i],DOS[sp][i]))
                f.close()

                # partial
                for ish in range(self.n_shells):
                    f=open('DOScorr%s_proj%s.dat'%(sp,ish),'w')
                    for i in range(n_om): f.write("%s    %s\n"%(mesh[i],DOSproj[ish][sp][i]))
                    f.close()

                    for i in range(self.shells[ish]['dim']):
                        for j in range(i,self.shells[ish]['dim']):
                            Fname = './DOScorr'+sp+'_proj'+str(ish)+'_'+str(i)+'_'+str(j)+'.dat'
                            f=open(Fname,'w')
                            for iom in range(n_om): f.write("%s    %s\n"%(mesh[iom],DOSproj_orb[ish][sp][iom,i,j]))
                            f.close()




    def spaghettis(self,broadening,shift=0.0,plot_range=None, ishell=None, invert_Akw=False, fermi_surface=False):
        """ Calculates the correlated band structure with a real-frequency self energy.
            ATTENTION: Many things from the original input file are overwritten!!!"""

        assert hasattr(self,"Sigma_imp_w"), "spaghettis: Set Sigma_imp_w first."
        things_to_read = ['n_k','n_orbitals','proj_mat','hopping','n_parproj','proj_mat_pc']
        value_read = self.read_input_from_hdf(subgrp=self.bands_data,things_to_read=things_to_read)
        if not value_read: return value_read

        if fermi_surface: ishell=None

        # FIXME CAN REMOVE?
        # print hamiltonian for checks:
        if self.SP == 1 and self.SO == 0:
            f1=open('hamup.dat','w')
            f2=open('hamdn.dat','w')

            for ik in range(self.n_k):
                for i in range(self.n_orbitals[ik,0]):
                    f1.write('%s    %s\n'%(ik,self.hopping[ik,0,i,i].real))
                for i in range(self.n_orbitals[ik,1]):
                    f2.write('%s    %s\n'%(ik,self.hopping[ik,1,i,i].real))
                f1.write('\n')
                f2.write('\n')
            f1.close()
            f2.close()
        else:
            f=open('ham.dat','w')
            for ik in range(self.n_k):
                for i in range(self.n_orbitals[ik,0]):
                    f.write('%s    %s\n'%(ik,self.hopping[ik,0,i,i].real))
                f.write('\n')
            f.close()


        #=========================================
        # calculate A(k,w):

        mu = self.chemical_potential
        spn = self.spin_block_names[self.SO]

        # init DOS:
        mesh = [x.real for x in self.Sigma_imp_w[0].mesh]
        n_om = len(mesh)

        if plot_range is None:
            om_minplot = mesh[0]-0.001
            om_maxplot = mesh[n_om-1] + 0.001
        else:
            om_minplot = plot_range[0]
            om_maxplot = plot_range[1]

        if ishell is None:
            Akw = {}
            for sp in spn: Akw[sp] = numpy.zeros([self.n_k, n_om ],numpy.float_)
        else:
            Akw = {}
            for sp in spn: Akw[sp] = numpy.zeros([self.shells[ishell]['dim'],self.n_k, n_om ],numpy.float_)

        if fermi_surface:
            om_minplot = -2.0*broadening
            om_maxplot =  2.0*broadening
            Akw = {}
            for sp in spn: Akw[sp] = numpy.zeros([self.n_k,1],numpy.float_)

        if not ishell is None:
            GFStruct_proj =  [ (sp, range(self.shells[ishell]['dim'])) for sp in spn ]
            Gproj = BlockGf(name_block_generator = [ (block,GfReFreq(indices = inner, mesh = self.Sigma_imp_w[0].mesh)) for block,inner in GFStruct_proj ], make_copies = False)
            Gproj.zero()

        for ik in range(self.n_k):

            G_latt_w = self.lattice_gf(ik=ik,mu=mu,iw_or_w="w",broadening=broadening)
            if ishell is None:
                # non-projected A(k,w)
                for iom in range(n_om):
                    if (mesh[iom] > om_minplot) and (mesh[iom] < om_maxplot):
                        if fermi_surface:
                            for bname,gf in G_latt_w: Akw[bname][ik,0] += gf.data[iom,:,:].imag.trace()/(-3.1415926535) * (mesh[1]-mesh[0])
                        else:
                            for bname,gf in G_latt_w: Akw[bname][ik,iom] += gf.data[iom,:,:].imag.trace()/(-3.1415926535)
                            Akw[bname][ik,iom] += ik*shift                       # shift Akw for plotting in xmgrace -- REMOVE


            else:
                # projected A(k,w):
                Gproj.zero()
                tmp = Gproj.copy()
                for ir in range(self.n_parproj[ishell]):
                    for bname,gf in tmp: tmp[bname] << self.downfold_pc(ik,ir,ishell,bname,G_latt_w[bname],gf)
                    Gproj += tmp

                # FIXME NEED TO READ IN ROTMAT_ALL FROM PARPROJ SUBGROUP, REPLACE ROTLOC WITH ROTLOC_ALL
                # TO BE FIXED:
                # rotate to local frame
                #if (self.use_rotations):
                #    for bname,gf in Gproj: Gproj[bname] << self.rotloc(0,gf,direction='toLocal')

                for iom in range(n_om):
                    if (mesh[iom] > om_minplot) and (mesh[iom] < om_maxplot):
                        for ish in range(self.shells[ishell]['dim']):
                            for ibn in spn:
                                Akw[ibn][ish,ik,iom] = Gproj[ibn].data[iom,ish,ish].imag/(-3.1415926535)


        # END k-LOOP
        if mpi.is_master_node():
            if ishell is None:

                for ibn in spn:
                    # loop over GF blocs:

                    if invert_Akw:
                        maxAkw=Akw[ibn].max()
                        minAkw=Akw[ibn].min()


                    # open file for storage:
                    if fermi_surface:
                        f=open('FS_'+ibn+'.dat','w')
                    else:
                        f=open('Akw_'+ibn+'.dat','w')

                    for ik in range(self.n_k):
                        if fermi_surface:
                            if invert_Akw:
                                Akw[ibn][ik,0] = 1.0/(minAkw-maxAkw)*(Akw[ibn][ik,0] - maxAkw)
                            f.write('%s    %s\n'%(ik,Akw[ibn][ik,0]))
                        else:
                            for iom in range(n_om):
                                if (mesh[iom] > om_minplot) and (mesh[iom] < om_maxplot):
                                    if invert_Akw:
                                        Akw[ibn][ik,iom] = 1.0/(minAkw-maxAkw)*(Akw[ibn][ik,iom] - maxAkw)
                                    if shift > 0.0001:
                                        f.write('%s      %s\n'%(mesh[iom],Akw[ibn][ik,iom]))
                                    else:
                                        f.write('%s     %s      %s\n'%(ik,mesh[iom],Akw[ibn][ik,iom]))

                            f.write('\n')

                    f.close()

            else:
                for ibn in spn:
                    for ish in range(self.shells[ishell]['dim']):

                        if invert_Akw:
                            maxAkw=Akw[ibn][ish,:,:].max()
                            minAkw=Akw[ibn][ish,:,:].min()

                        f=open('Akw_'+ibn+'_proj'+str(ish)+'.dat','w')

                        for ik in range(self.n_k):
                            for iom in range(n_om):
                                if (mesh[iom] > om_minplot) and (mesh[iom] < om_maxplot):
                                    if invert_Akw:
                                        Akw[ibn][ish,ik,iom] = 1.0/(minAkw-maxAkw)*(Akw[ibn][ish,ik,iom] - maxAkw)
                                    if shift > 0.0001:
                                        f.write('%s      %s\n'%(mesh[iom],Akw[ibn][ish,ik,iom]))
                                    else:
                                        f.write('%s     %s      %s\n'%(ik,mesh[iom],Akw[ibn][ish,ik,iom]))

                            f.write('\n')

                        f.close()


    def partial_charges(self,beta=40):
        """Calculates the orbitally-resolved density matrix for all the orbitals considered in the input.
           The theta-projectors are used, hence case.parproj data is necessary"""

        value_read = self.read_parproj_input_from_hdf()
        if not value_read: return value_read
        if self.symm_op: self.symmpar = Symmetry(self.hdf_file,subgroup=self.symmpar_data)

        # Density matrix in the window
        spn = self.spin_block_names[self.SO]
        ntoi = self.spin_names_to_ind[self.SO]
        self.dens_mat_window = [ [numpy.zeros([self.shells[ish]['dim'],self.shells[ish]['dim']],numpy.complex_) for ish in range(self.n_shells)]
                                 for isp in range(len(spn)) ]    # init the density matrix

        mu = self.chemical_potential
        GFStruct_proj = [ [ (sp, range(self.shells[i]['dim'])) for sp in spn ]  for i in range(self.n_shells) ]
        if hasattr(self,"Sigma_imp_iw"):
            Gproj = [BlockGf(name_block_generator = [ (block,GfImFreq(indices = inner, mesh = self.Sigma_imp_iw[0].mesh)) for block,inner in GFStruct_proj[ish] ], make_copies = False)
                     for ish in range(self.n_shells)]
            beta = self.Sigma_imp_iw[0].mesh.beta
        else:
            Gproj = [BlockGf(name_block_generator = [ (block,GfImFreq(indices = inner, beta = beta)) for block,inner in GFStruct_proj[ish] ], make_copies = False)
                     for ish in range(self.n_shells)]

        for ish in range(self.n_shells): Gproj[ish].zero()

        ikarray=numpy.array(range(self.n_k))

        for ik in mpi.slice_array(ikarray):
            G_latt_iw = self.lattice_gf(ik=ik,mu=mu,iw_or_w="iw",beta=beta)
            G_latt_iw *= self.bz_weights[ik]

            for ish in range(self.n_shells):
                tmp = Gproj[ish].copy()
                for ir in range(self.n_parproj[ish]):
                    for bname,gf in tmp: tmp[bname] << self.downfold_pc(ik,ir,ish,bname,G_latt_iw[bname],gf)
                    Gproj[ish] += tmp

        #collect data from mpi:
        for ish in range(self.n_shells):
            Gproj[ish] << mpi.all_reduce(mpi.world, Gproj[ish], lambda x,y : x+y)
        mpi.barrier()


        # Symmetrisation:
        if self.symm_op != 0: Gproj = self.symmpar.symmetrize(Gproj)

        for ish in range(self.n_shells):

            # Rotation to local:
            if self.use_rotations:
                for bname,gf in Gproj[ish]: Gproj[ish][bname] << self.rotloc_all(ish,gf,direction='toLocal')

            isp = 0
            for bname,gf in Gproj[ish]: #dmg.append(Gproj[ish].density()[bname])
                self.dens_mat_window[isp][ish] = Gproj[ish].density()[bname]
                isp+=1

        # add Density matrices to get the total:
        dens_mat = [ [ self.dens_mat_below[ntoi[spn[isp]]][ish]+self.dens_mat_window[isp][ish] for ish in range(self.n_shells)]
                     for isp in range(len(spn)) ]

        return dens_mat

# ----------------- transport -----------------------

    def read_transport_input_from_hdf(self):
        """
        Reads the data for transport calculations from the HDF file
        """

        thingstoread = ['bandwin','bandwin_opt','kp','latticeangles','latticeconstants','latticetype','nsymm','symmcartesian','vk']
        retval = self.read_input_from_hdf(subgrp=self.transp_data,things_to_read = thingstoread)
        return retval
    
    
    def cellvolume(self, latticetype, latticeconstants, latticeangle):
        """
        Calculate cell volume: volumecc conventional cell, volumepc, primitive cell.
        """
        a = latticeconstants[0]
        b = latticeconstants[1]
        c = latticeconstants[2]
        c_al = numpy.cos(latticeangle[0])
        c_be = numpy.cos(latticeangle[1])
        c_ga = numpy.cos(latticeangle[2])
        volumecc = a * b * c * numpy.sqrt(1 + 2 * c_al * c_be * c_ga - c_al ** 2 - c_be * 82 - c_ga ** 2)
      
        det = {"P":1, "F":4, "B":2, "R":3, "H":1, "CXY":2, "CYZ":2, "CXZ":2}
        volumepc = volumecc / det[latticetype]
      
        return volumecc, volumepc


    def transport_distribution(self, dir_list=[(0,0)], broadening=0.01, energywindow=None, Om_mesh=[0.0], beta=40, with_Sigma=False, n_om=None):
        """calculate Tr A(k,w) v(k) A(k, w+q) v(k) and optics.
        energywindow: regime for omega integral
        Om_mesh: contains the frequencies of the optic conductivitity. Om_mesh is repinned to the self-energy mesh
        (hence exact values might be different from those given in Om_mesh)
        dir_list: list to defines the indices of directions. xx,yy,zz,xy,yz,zx. 
        ((0, 0) --> xx, (1, 1) --> yy, (0, 2) --> xz, default: (0, 0))
        with_Sigma: Use Sigma = 0 if False
        """
       
        # Check if wien converter was called
        if mpi.is_master_node():
            ar = HDFArchive(self.hdf_file, 'a')
            if not (self.transp_data in ar): raise IOError, "No %s subgroup in hdf file found! Call convert_transp_input first." %self.transp_data
        
        self.dir_list = dir_list
        
        self.read_transport_input_from_hdf()
        velocities = self.vk
        n_inequiv_spin_blocks = self.SP + 1 - self.SO  # up and down are equivalent if SP = 0
        
            
        # calculate A(k,w)
        #######################################
        
        # use k-dependent-projections.
        assert self.k_dep_projection == 1, "Not implemented!"

        # Define mesh for Greens function and the used energy range
        if (with_Sigma == True):
            self.omega = numpy.array([round(x.real,12) for x in self.Sigma_imp_w[0].mesh])
            mu = self.chemical_potential
            n_om = len(self.omega)
            print "Using omega mesh provided by Sigma."

            if energywindow is not None:
                # Find according window in Sigma mesh
                ioffset = numpy.sum(self.omega < energywindow[0])
                self.omega = self.omega[numpy.logical_and(self.omega >= energywindow[0], self.omega <= energywindow[1])]
                n_om = len(self.omega)
                
                # Truncate Sigma to given omega window
                for icrsh in range(self.n_corr_shells):
                    Sigma_save = self.Sigma_imp_w[icrsh].copy()
                    spn = self.spin_block_names[self.corr_shells[icrsh]['SO']]
                    glist = lambda : [ GfReFreq(indices = inner, window=(self.omega[0], self.omega[-1]),n_points=n_om) for block, inner in self.gf_struct_sumk[icrsh]]
                    self.Sigma_imp_w[icrsh] = BlockGf(name_list = spn, block_list = glist(),make_copies=False)
                    for i,g in self.Sigma_imp_w[icrsh]:
                        for iL in g.indices:
                            for iR in g.indices:
                                for iom in xrange(n_om):
                                    g.data[iom,iL,iR] = Sigma_save[i].data[ioffset+iom,iL,iR] # FIXME IS THIS CLEAN? MANIPULATING data DIRECTLY?
            
        else:
            assert n_om is not None, "Number of omega points (n_om) needed!"
            assert energywindow is not None, "Energy window needed!" 
            self.omega = numpy.linspace(energywindow[0],energywindow[1],n_om)
            mu = 0.0

        if (abs(self.fermi_dis(self.omega[0]*beta)*self.fermi_dis(-self.omega[0]*beta)) > 1e-5
            or abs(self.fermi_dis(self.omega[-1]*beta)*self.fermi_dis(-self.omega[-1]*beta)) > 1e-5):
                print "\n##########################################"
                print "WARNING: Energywindow might be too narrow!"
                print "##########################################\n"

        d_omega = round(numpy.abs(self.omega[0] - self.omega[1]), 12)

        # define exact mesh for optic conductivity
        Om_mesh_ex = numpy.array([int(x / d_omega) for x in Om_mesh])
        self.Om_meshr= Om_mesh_ex*d_omega

        if mpi.is_master_node():
            print "Chemical potential: ", mu
            print "Using n_om = %s points in the energywindow [%s,%s]"%(n_om, self.omega[0], self.omega[-1])
            print "omega vector is:"
            print self.omega
            print "Omega mesh interval  ", d_omega
            print "Provided Om_mesh   ", numpy.array(Om_mesh)
            print "Pinnend Om_mesh to  ", self.Om_meshr
        
        # output P(\omega)_xy should have the same dimension as defined in mshape.
        self.Pw_optic = numpy.zeros((len(dir_list), len(Om_mesh_ex), n_om), dtype=numpy.float_)
    
        ik = 0
        
        spn = self.spin_block_names[self.SO]
        ntoi = self.spin_names_to_ind[self.SO]
          
        G_w = BlockGf(name_block_generator=[(spn[isp], GfReFreq(indices=range(self.n_orbitals[ik][isp]), window=(self.omega[0], self.omega[-1]), n_points = n_om)) 
                for isp in range(n_inequiv_spin_blocks) ], make_copies=False)
        mupat = [numpy.identity(self.n_orbitals[ik][isp], numpy.complex_) * mu for isp in range(n_inequiv_spin_blocks)] # construct mupat
        Annkw = [numpy.zeros((self.n_orbitals[ik][isp], self.n_orbitals[ik][isp], n_om), dtype=numpy.complex_) for isp in range(n_inequiv_spin_blocks)]
        
        ikarray = numpy.array(range(self.n_k))
        for ik in mpi.slice_array(ikarray):
            unchangedsize = all([ self.n_orbitals[ik][isp] == mupat[isp].shape[0] for isp in range(n_inequiv_spin_blocks)])
            if not unchangedsize:
               # recontruct green functions.
               G_w = BlockGf(name_block_generator=[(spn[isp], GfReFreq(indices=range(self.n_orbitals[ik][isp]), window = (self.omega[0], self.omega[-1]), n_points = n_om)) 
                       for isp in range(n_inequiv_spin_blocks) ], make_copies=False)
               # construct mupat
               mupat = [numpy.identity(self.n_orbitals[ik][isp], numpy.complex_) * mu for isp in range(n_inequiv_spin_blocks)]
               #set a temporary array storing spectral functions with band index. Note, usually we should have spin index
               Annkw = [numpy.zeros((self.n_orbitals[ik][isp], self.n_orbitals[ik][isp], n_om), dtype=numpy.complex_) for isp in range(n_inequiv_spin_blocks)]
               # get lattice green function
            
            G_w << 1*Omega + 1j*broadening
            
            MS = copy.deepcopy(mupat)
            for ibl in range(n_inequiv_spin_blocks):
                ind = ntoi[spn[ibl]]
                n_orb = self.n_orbitals[ik][ibl]
                MS[ibl] = self.hopping[ik,ind,0:n_orb,0:n_orb].real - mupat[ibl]
            G_w -= MS
            
            if (with_Sigma == True):
                tmp = G_w.copy()    # init temporary storage
                # form self energy from impurity self energy and double counting term.
                sigma_minus_dc = self.add_dc(iw_or_w="w")
                # substract self energy
                for icrsh in range(self.n_corr_shells):
                    for sig, gf in tmp: tmp[sig] << self.upfold(ik, icrsh, sig, sigma_minus_dc[icrsh][sig], gf)
                    G_w -= tmp

            G_w.invert()

            for isp in range(n_inequiv_spin_blocks):
                Annkw[isp].real = -copy.deepcopy(G_w[self.spin_block_names[self.SO][isp]].data.swapaxes(0,1).swapaxes(1,2)).imag / numpy.pi
            
            for isp in range(n_inequiv_spin_blocks):
                kvel = velocities[isp][ik]
                Pwtem = numpy.zeros((len(dir_list), len(Om_mesh_ex), n_om), dtype=numpy.float_)
                
                bmin = max(self.bandwin[isp][ik, 0], self.bandwin_opt[isp][ik, 0])
                bmax = min(self.bandwin[isp][ik, 1], self.bandwin_opt[isp][ik, 1])
                Astart = bmin - self.bandwin[isp][ik, 0]
                Aend = bmax - self.bandwin[isp][ik, 0] + 1
                vstart = bmin - self.bandwin_opt[isp][ik, 0]
                vend = bmax - self.bandwin_opt[isp][ik, 0] + 1

                #symmetry loop
                for Rmat in self.symmcartesian:
                    # get new velocity.
                    Rkvel = copy.deepcopy(kvel)
                    for vnb1 in range(self.bandwin_opt[isp][ik, 1] - self.bandwin_opt[isp][ik, 0] + 1):
                        for vnb2 in range(self.bandwin_opt[isp][ik, 1] - self.bandwin_opt[isp][ik, 0] + 1):
                            Rkvel[vnb1][vnb2][:] = numpy.dot(Rmat, Rkvel[vnb1][vnb2][:])
                    ipw = 0
                    for (ir, ic) in dir_list:
                        for iw in xrange(n_om):
                            for iq in range(len(Om_mesh_ex)):
                                if(iw + Om_mesh_ex[iq] >= n_om):
                                    continue
                                 
                                # construct matrix for A and velocity.
                                Annkwl = Annkw[isp][Astart:Aend, Astart:Aend, iw]
                                Annkwr = Annkw[isp][Astart:Aend, Astart:Aend, iw + Om_mesh_ex[iq]]
                                Rkveltr = Rkvel[vstart:vend, vstart:vend, ir]
                                Rkveltc = Rkvel[vstart:vend, vstart:vend, ic]
                                # print Annkwl.shape, Annkwr.shape, Rkveltr.shape, Rkveltc.shape
                                Pwtem[ipw, iq, iw] += numpy.dot(numpy.dot(numpy.dot(Rkveltr, Annkwl), Rkveltc), Annkwr).trace().real
                        ipw += 1
                        
                # k sum and spin sum.
                self.Pw_optic += Pwtem * self.bz_weights[ik] / self.nsymm
        
        self.Pw_optic = mpi.all_reduce(mpi.world, self.Pw_optic, lambda x, y : x + y)
        self.Pw_optic *= (2 - self.SP)
        

    def conductivity_and_seebeck(self, beta=40):
        """ #return 1/T*A0, that is Conductivity in unit 1/V
        calculate, save and return Conductivity
        """

        if mpi.is_master_node():
           assert hasattr(self,'Pw_optic'), "Run transport_distribution first or load data from h5!"
	   assert hasattr(self,'latticetype'), "Run convert_transp_input first or load data from h5!"

           volcc, volpc  = self.cellvolume(self.latticetype, self.latticeconstants, self.latticeangles)

           n_direction, n_q, n_w= self.Pw_optic.shape 
           omegaT = self.omega * beta
           A0 = numpy.zeros((n_direction,n_q), dtype=numpy.float_)
           q_0 = False
           self.seebeck = numpy.zeros((n_direction,), dtype=numpy.float_)
           self.seebeck[:] = numpy.NAN

           d_omega = self.omega[1] - self.omega[0]
           for iq in xrange(n_q):
               # treat q = 0,  caclulate conductivity and seebeck
               if (self.Om_meshr[iq] == 0.0):
                   # if Om_meshr contains multiple entries with w=0, A1 is overwritten!
                   q_0 = True
                   A1 = numpy.zeros((n_direction,), dtype=numpy.float_)
                   for idir in range(n_direction):
                       for iw in xrange(n_w):
                           A0[idir, iq] += beta * self.Pw_optic[idir, iq, iw] * self.fermi_dis(omegaT[iw]) * self.fermi_dis(-omegaT[iw])
                           A1[idir] += beta * self.Pw_optic[idir, iq, iw] *  self.fermi_dis(omegaT[iw]) * self.fermi_dis(-omegaT[iw]) * numpy.float(omegaT[iw])
                       self.seebeck[idir] = -A1[idir] / A0[idir, iq]
                       print "A0", A0[idir, iq] *d_omega/beta
                       print "A1", A1[idir] *d_omega/beta
               # treat q ~= 0, calculate optical conductivity
               else:
                   for idir in range(n_direction):
                       for iw in xrange(n_w):
                           A0[idir, iq] += self.Pw_optic[idir, iq, iw] * (self.fermi_dis(omegaT[iw]) - self.fermi_dis(omegaT[iw] + self.Om_meshr[iq] * beta)) / self.Om_meshr[iq]

           A0 *= d_omega
           #cond = beta * self.tdintegral(beta, 0)[index]
           print "V in bohr^3          ", volpc
           # transform to standard unit as in resistivity
           self.optic_cond = A0 * 10700.0 / volpc
           self.seebeck *= 86.17

           # print
           for im in range(n_direction):
               for iq in xrange(n_q):
                   print "Conductivity in direction %s for Om_mesh %d       %.4f  x 10^4 Ohm^-1 cm^-1" % (self.dir_list[im], iq, self.optic_cond[im, iq])
                   print "Resistivity in direction  %s for Om_mesh %d       %.4f  x 10^-4 Ohm cm" % (self.dir_list[im], iq, 1.0 / self.optic_cond[im, iq])
               if q_0:
                   print "Seebeck in direction      %s for q = 0            %.4f  x 10^(-6) V/K" % (self.dir_list[im], self.seebeck[im])
           

    def fermi_dis(self, x):
        return 1.0/(numpy.exp(x)+1)
    
