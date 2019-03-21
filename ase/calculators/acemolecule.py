from __future__ import print_function
import os
from copy import deepcopy
#from ase.atoms import Atoms
from ase.io.acemolecule import read_acemolecule_out
from ase.calculators.calculator import ReadError
from ase.calculators.calculator import FileIOCalculator
#import numpy as np


class ACE(FileIOCalculator):
    '''
    ACE-Molecule logfile reader
    '''
    name = 'ace'
    implemented_properties = ['energy', 'forces',
                              'geometry', 'excitation-energy']
#    system_changes = None
    # defaults is default value of ACE-input
    basic_list = [{
        'Type': 'Scaling', 'Scaling': '0.35', 'Basis': 'Sinc',
                  'Grid': 'Sphere',
                  'KineticMatrix': 'Finite_Difference', 'DerivativesOrder': '7',
                  'GeometryFilename': None, 'NumElectrons': None}
                  ]
    guess_list = [{}]  # now not need this
    scf_list = [{
        'ExchangeCorrelation': {'XFunctional': 'GGA_X_PBE', 'CFunctional': 'GGA_C_PBE'},
        'NumberOfEigenvalues': None,
    }]

    force_list = [{'ForceDerivative': 'Potential'}]
    tddft_list = [{
        'SortOrbital': 'Order', 'MaximumOrder': '10',
        'ExchangeCorrelation': {'XFunctional': 'GGA_X_PBE', 'CFunctional': 'GGA_C_PBE'},
    }]
    order_list = ['BasicInformation', 'Guess', 'Scf']
    cis_list = [{}]
    cisd_list = [{}]
    dda_list = [{}]

    default_parameters = {'BasicInformation': basic_list, 'Guess': guess_list,
                          'Scf': scf_list, 'Force': force_list, 'TDDFT': tddft_list, 'order': order_list}
    parameters = default_parameters
    command = 'mpirun -np 1 ../ace PREFIX.inp > PREFIX.log'

    def __init__(
            self, restart=None, ignore_bad_restart_file=False,
            label='ace', atoms=None, command=None,
            basisfile=None, **kwargs):
        FileIOCalculator.__init__(self, restart, ignore_bad_restart_file,
                                  label, atoms, command=command, **kwargs)


    def get_property(self, name, atoms=None, allow_calculation=True):
        '''Make input, xyz after that calculate and get_property(energy, forces, and so on)'''
        force_in_param = 0
        if(name=='forces'):
            if not 'Force' in self.parameters["order"]:
                self.parameters['order'].append('Force')
                force_in_param = 1
        self.results = {}
        self.write_input(atoms)
        result = super().get_property(name, atoms, allow_calculation)
        if force_in_param:
            self.parameters['order'].pop()

        return result

    def set(self, **kwargs):
        new_parameters = deepcopy(self.parameters)
        changed_parameters = FileIOCalculator.set(self, **kwargs)
        if 'order' in kwargs:
            new_parameters['order'] = kwargs['order']
            append_default_parameter = list(set(kwargs['order']))
            for value in append_default_parameter:
                ##### This is for adding default values of repeated section
                repeat = kwargs['order'].count(value)
                if(repeat-1 > 0):
                    for i in range(repeat-1):
                        if value in self.default_parameters.keys():
                            new_parameters[value] += self.default_parameters[value]
        for key in new_parameters['order']: 
            if key in kwargs.keys():      # key : BasicInformation, Force, Scf and so on
                if isinstance(kwargs[key], dict):
                    dict_to_list = []
                    dict_to_list.append(kwargs[key])
                    kwargs[key] = dict_to_list         # kwargs[key] : basic_list, force_lsit ....
                i = 0
                for val in kwargs[key]:
                    if(len(new_parameters[key])>0):
                        new_parameters[key][i] = update_recursively(new_parameters[key][i], val)
                    else:    
                        new_parameters[key] = [val] 
                    i = i+1
        self.parameters = new_parameters
        return changed_parameters

    def read(self, label):
        FileIOCalculator.read(self, label)
        filename = self.label + ".log"
        if not os.path.isfile(filename):
            raise ReadError
        self.read_results()

    def make_xyz_file(self, atoms):
        atoms.write("{}_opt.xyz".format(self.label))

    def write_input(self, atoms, properties=None, system_changes=None):
        '''Writes the input file and xyz file'''
        FileIOCalculator.write_input(self, atoms, properties, system_changes)
        inputfile = open(self.label + '.inp', 'w')
        self.make_xyz_file(atoms)
        self.parameters["BasicInformation"][0]["GeometryFilename"] = "{}_opt.xyz".format(
            self.label)
        self.parameters["BasicInformation"][0]["GeometryFormat"] = "xyz"
        self.write_acemolecule_input(inputfile, self.parameters)

        inputfile.close()

    def read_results(self):
        '''Read results from logfile '''
        filename = self.label + '.log'
        f = open(filename, "r")
        tddft = len(f.read().split("TDDFT"))
        if tddft > 2 :
            quantities = ['excitation-energy']
        else:
            quantities = ['energy', 'forces', 'atoms', 'excitation-energy']
        for value in quantities:
            self.results[value] = read_acemolecule_out(
                filename, quantity=value)

    def write_acemolecule_section(self, fpt, section, indent=0):
        for key, val in section.items():
            if isinstance(val, str) or isinstance(val, int) or isinstance(val, float):
                fpt.write('    ' * indent + str(key) + " " + str(val) + "\n")
            elif isinstance(val, dict):
                fpt.write('    ' * indent + "%% " + str(key) + "\n")
                self.write_acemolecule_section(fpt, val, indent + 1)
                fpt.write('    ' * indent + "%% End\n")

        return

    def write_acemolecule_input(self, fpt, param2, indent=0):
        prefix = "    " * indent
        param = deepcopy(param2)
        for i in range(len(param['order'])):
            fpt.write(prefix + "%% " + param['order'][i] + "\n")
            section_list = param[param['order'][i]]
            if(len(section_list) > 0):
                section = section_list.pop(0)
                self.write_acemolecule_section(fpt, section, 1)
            fpt.write("%% End\n")
        return


def update_recursively(oldpar, newpar):
    for key, val in newpar.items():
        if isinstance(val, dict):
            print('update_recursively if')
            if isinstance(oldpar.get(key), dict):
                update_recursively(old, val)
            else:
                oldpar[key] = val
        else:
            oldpar[key] = val
    return oldpar









if __name__ == "__main__":
    old = {
        'Type': 'Scaling', 'Scaling': '0.35', 'Basis': 'Sinc',
                  'Grid': 'Sphere',
                  'KineticMatrix': 'Finite_Difference', 'DerivativesOrder': '7',
                  'GeometryFilename': None, 'NumElectrons': None}
    new = dict(GeometryFilename= '/home/khs/hs_file/programs/ACE-Molecule/aseinput/tddft_example/xyz/benzene.xyz')
    old = update_recursively(old,new)
    print(old)
    new = {'Pseudopotential' : {'Pseudopotential':1,'Format': 'upf', 'PSFilePath':'/home/khs/DATA/UPF', 'PSFileSuffix':'.pbe-theos.UPF'}}
    old = update_recursively(old,new)
    print(old)
    


