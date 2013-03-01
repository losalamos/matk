__all__ = ['read_dakota', 'read_model_files', 'write_model_files', 'ModelTemplate', 'ModelInstruction']

import pymads
import re
from numpy import array, where

def read_dakota(filename):
    """ Read a DAKOTA control file and populate objects
    
    First argument must be a DAKOTA input file
    Optional second argument is a pymads dakota_prob (pymads.dakota_prob)
    """
    f = open(filename, 'r')
    lines = array(f.readlines())

    i = 0
    while i < lines.size:
        values = lines[i].split()
        if values:
            if 'method,' in values[0]:
                print values[0] 
            if 'variables,' in values[0]:
                print values[0]
            if 'interface,' in values[0]:
               print values[0] 
            if 'responses,' in values[0]:
               print values[0] 
        i+=1

    f.close()

 

def read_model_files(prob, workdir=None):
    """ Collect simulated values from model files using
        pest instruction file

            Parameter
            ---------
            workdir : string
                name of directory where model output files exist            
    """
    for insfl in prob.insfile:
        line_index = -1
        if workdir:
            filename = workdir + '/' + insfl.modelflname
        else:
            filename = insfl.modelflname
        f = open( filename , 'r')
        model_file_lines = array(f.readlines())
        for line in insfl.lines:
            col_index = 0
            values = line.split()
            for val in values:
                if 'l' in val:
                    line_index += int(re.sub("l","", val))
                if 'w' in val:
                    col_index += 1
                if '!' in val:
                    obsnm = re.sub("!","", val)
                    values = model_file_lines[line_index].split()
                    prob.set_sim_value( obsnm, values[col_index])

def write_model_files(prob, workdir=None):
    """ Write model from pest template file using current values

            Parameter
            ---------
            workdir : string
                name of directory to write model files to           
    """
    for tplfl in prob.tplfile:
        model_file_str = ''
        for line in tplfl.lines:
            model_file_str += line
        for par in prob.get_parameters():
            model_file_str = re.sub(tplfl.marker + r'.*' + par.name + r'.*' + tplfl.marker, 
                                        str(par.value), model_file_str)
        if workdir:
            filename = workdir + '/' + tplfl.modelflname
        else:
            filename = tplfl.modelflname
        f = open( filename, 'w')
        f.write(model_file_str)
        
class ModelInstruction(object):
    """pymads PEST instruction file class
    """
    def __init__(self,insflname,modelflname):
        self.insflname = insflname
        self.modelflname = modelflname
        f = open( self.insflname, 'r')
        self.lines = f.readlines()
        lines = array(self.lines)
        values = self.lines[0].split()
        self.lines = lines[1:]
        if values[0] != 'pif':
            print "%s doesn't appear to be a PEST instruction file" % self.insflname
            return 0
        self.marker = values[1]
    @property
    def insflname(self):
        return self._insflname
    @insflname.setter
    def insflname(self,value):
        self._insflname = value
    @property
    def modelflname(self):
        return self._modelflname
    @modelflname.setter
    def modelflname(self,value):
        self._modelflname = value
    @property
    def marker(self):
        return self._marker
    @marker.setter
    def marker(self,value):
        self._marker = value 

class ModelTemplate(object):
    """pymads Template file class
    """
    def __init__(self,tplflname,modelflname):
        self.tplflname = tplflname
        self.modelflname = modelflname
        f = open( self.tplflname, 'r')
        self.lines = f.readlines()
        lines = array(self.lines)
        values = self.lines[0].split()
        self.lines = lines[1:]
        if values[0] != 'ptf':
            print "%s doesn't appear to be a PEST template file" % self.tplflname
            return 0
        self.marker = values[1]
    @property
    def tplflname(self):
        return self._tplflname
    @tplflname.setter
    def tplflname(self,value):
        self._tplflname = value
    @property
    def modelflname(self):
        return self._modelflname
    @modelflname.setter
    def modelflname(self,value):
        self._modelflname = value
    @property
    def marker(self):
        return self._marker
    @marker.setter
    def marker(self,value):
        self._marker = value 
 
def obj_fun(prob):
    of = 0.0
    for obsgrp in prob.obsgrp:
        for obs in obsgrp.observation:
            of += ( float(obs.value) - float(obs.sim_value) )**2
    return of
            
 
def main(argv=None):
    import sys
    if argv is None:
        argv = sys.argv
    pest_prob = read_pest(argv[1])
    print pest_prob

if __name__ == "__main__":
    main()
 
