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

from numpy import *
from pytriqs.applications.dft.converters.wien2k_converter import *
from pytriqs.applications.dft.sumk_dft import *
from pytriqs.applications.dft.sumk_dft_tools import *

beta = 40

Converter = Wien2kConverter(filename='SrVO3', repacking=True)
Converter.convert_dft_input()
Converter.convert_transport_input()

SK = SumkDFTTools(hdf_file='SrVO3.h5', use_dft_blocks=True)

ar = HDFArchive('SrVO3_Sigma.h5', 'a')
Sigma = ar['dmft_transp_input']['Sigma_w']
SK.put_Sigma(Sigma_imp = [Sigma])
SK.chemical_potential = ar['dmft_transp_input']['chemical_potential']
SK.dc_imp = ar['dmft_transp_input']['dc_imp']
del ar

SK.transport_distribution(directions=['xx'], broadening=0.0, energy_window=[-0.3,0.3], Om_mesh=[0.00, 0.02] , beta=beta, with_Sigma=True)
#SK.save(['Gamma_w','Om_meshr','omega','directions'])
#SK.load(['Gamma_w','Om_meshr','omega','directions'])
SK.conductivity_and_seebeck(beta=beta)
SK.hdf_file = 'srvo3_transp.output.h5'
SK.save(['seebeck','optic_cond'])

