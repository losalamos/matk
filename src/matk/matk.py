import sys, os
import pdb
from parameter import Parameter
from observation import Observation
from sampleset import SampleSet
import numpy 
from lhs import *
import cPickle as pickle
from shutil import rmtree
import itertools
from multiprocessing import Process, Manager, Pool, freeze_support
from multiprocessing.queues import Queue, JoinableQueue
import traceback
from copy import deepcopy
import pest_io
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from lmfit.asteval import Interpreter

class matk(object):
    """ Class for Model Analysis ToolKit (MATK) module
    """
    def __init__(self, model='', model_args=None, model_kwargs=None, cpus=1,
                 workdir_base=None, workdir=None, results_file=None,
                 seed=None, sample_size=10, hosts={}):
        '''Initialize MATK object
        :param model: Python function whose first argument is a dictionary of parameters and returns model outputs
        :type model: str
        :param model_args: additional arguments to model
        :type model_args: any
        :param model_kwargs: additional keyword arguments to model
        :type model_kwargs: any
        :param cpus: number of cpus to use
        :type cpus: int
        :param workdir_base: Base name of directory to use for model runs (parallel run case), run numbers are appended to base name
        :type workdir_base: str
        :param workdir: Name of directory to use for model runs (serial run case)
        :type workdir: str
        :param results_file: Name of file to write results
        :type results_file: str
        :param seed: Seed for random number generator
        :type seed: int
        :param sample_size: Size of sample to generate
        :type sample_size: int
        :param hosts: Host names to run on (i.e. on a cluster), hostname provided as kwarg to model (hostname=<hostname>)
        :type hosts: lst(str)
        :returns: object -- MATK object
        '''
        self.model = model
        self.model_args = model_args
        self.model_kwargs = model_kwargs
        self.cpus = cpus
        self.workdir_base = workdir_base
        self.workdir = workdir
        self.results_file = results_file
        self.seed = seed
        self.sample_size = sample_size
        self.hosts = hosts
      
        self.pars = OrderedDict()
        self.obs = OrderedDict()
        self.sampleset = OrderedDict()
        self.workdir_index = 0
        self._current = False # Flag indicating if simulated values are associated with current parameters
    @property
    def model(self):
        """ Python function that runs model
        """
        return self._model
    @model.setter
    def model(self,value):
        self._model = value       
    @property
    def model_args(self):
        """ Tuple of extra arguments to MATK model expected to come after parameter dictionary
        """
        return self._model_args
    @model_args.setter
    def model_args(self,value):
        if value is None:
            self._model_args = value
        elif not isinstance( value, (tuple,list,numpy.ndarray) ):
            print "Error: Expected list or array for model keyword arguments"
            return
        else:
            self._model_args = value
    @property
    def model_kwargs(self):
        """ Dictionary of extra keyword arguments to MATK model expected to come after parameter dictionary and model_args
        """
        return self._model_kwargs
    @model_kwargs.setter
    def model_kwargs(self,value):
        if value is None:
            self._model_kwargs = value       
        elif not isinstance( value, dict ):
            print "Error: Expected dictionary for model keyword arguments"
            return
        else:
            self._model_kwargs = value       
    @property
    def cpus(self):
        """ Set number of cpus to use for concurrent model evaluations
        """
        return self._cpus
    @cpus.setter
    def cpus(self,value):
        self._cpus = value
    @property
    def workdir_base(self):
        """ Set the base name for parallel working directories
        """
        return self._workdir_base
    @workdir_base.setter
    def workdir_base(self,value):
        self._workdir_base = value    
    @property
    def workdir(self):
        """ Set the base name for parallel working directories
        """
        return self._workdir
    @workdir.setter
    def workdir(self,value):
        self._workdir = value    
    @property
    def workdir_index(self):
        """ Set the working directory index for parallel runs    
        """
        return self._workdir_index
    @workdir_index.setter
    def workdir_index(self,value):
        self._workdir_index = value
    @property
    def results_file(self):
        """ Set the name of the results_file for parallel runs   
        """
        return self._results_file
    @results_file.setter
    def results_file(self,value):
        self._results_file = value
    @property
    def seed(self):
        """ Set the seed for random sampling
        """
        return self._seed
    @seed.setter
    def seed(self,value):
        self._seed = value
    @property
    def ssr(self):
        """ Sum of squared residuals
        """
        return sum(numpy.array(self.residuals)**2)
    def add_par(self, name, value=None, vary=True, min=None, max=None, expr=None, discrete_vals=[], discrete_counts=[], **kwargs):
        """ Add parameter to problem

            :param name: Name of parameter
            :type name: str
            :param value: Initial parameter value
            :type value: float
            :param vary: Whether parameter should be varied or not, currently only used with lmfit
            :type vary: bool
            :param min: Minimum bound
            :type min: float
            :param max: Maximum bound
            :type max: float
            :param expr: Mathematical expression to use to calculate parameter value
            :type expr: str
            :param discrete_vals: list of values defining histogram bins
            :type discrete_vals: [float]
            :param discrete_counts: list of counts associated with discrete_vals
            :type discrete_counts: [int]
            :param kwargs: keyword arguments passed to parameter class
        """
        if name in self.pars: 
            self.pars[name] = Parameter(name,parent=self,value=value,vary=vary,min=min,max=max,expr=expr,discrete_vals=[],discrete_counts=[],**kwargs)
        else:
            self.pars.__setitem__( name, Parameter(name,parent=self,value=value,vary=vary,min=min,max=max,expr=expr,discrete_vals=[],discrete_counts=[],**kwargs))
    def add_obs(self,name, sim=None, weight=1.0, value=None):
        ''' Add observation to problem
            
            :param name: Observation name
            :type name: str
            :param sim: Simulated value
            :type sim: fl64
            :param weight: Observation weight
            :type weight: fl64
            :param value: Value of observation
            :type value: fl64
            :returns: Observation object
        '''
        if name in self.obs: 
            self.obs[name] = Observation(name,sim=sim,weight=weight,value=value)
        else:
            self.obs.__setitem__( name, Observation(name,sim=sim,weight=weight,value=value))
    def create_sampleset(self,samples,name=None,responses=None,indices=None,index_start=1):
        """ Add sample set to problem
            
            :param name: Name of sample set
            :type name: str
            :param samples: Matrix of parameter samples with npar columns in order of matk.pars.keys()
            :type samples: list(fl64),ndarray(fl64)
            :param responses: Matrix of associated responses with nobs columns in order matk.obs.keys() if observation exists (existence of observations is not required) 
            :type responses: list(fl64),ndarray(fl64)
            :param indices: Sample indices to use when creating working directories and output files
            :type indices: list(int),ndarray(int)
        """
        if not isinstance( samples, (list,numpy.ndarray)):
            print "Error: Parameter samples are not a list or ndarray"
            return 1
        npar = len(self.pars)
        # If list, convert to ndarray
        if isinstance( samples, list ):
            samples = numpy.array(samples)
        if not samples.shape[1] == npar:
            print "Error: The number of columns in sample is not equal to the number of parameters in the problem"
            return 1
        if name is None:
            ind = str(len(self.sampleset))
            name = 'ss'+str(ind)
            while name in self.sampleset:
                ind += 1
                name = 'ss'+str(ind)
        if len(self.pars) > 0:
            parnames = self.parnames
        else:
            parnames = None
        if len(self.obs) > 0:
            obsnames = self.obsnames
        else:
            obsnames = None
        if name in self.sampleset: 
            self.sampleset[name] = SampleSet(name,samples,parent=self,responses=responses,
                                             indices=indices,index_start=index_start)
        else:
            self.sampleset.__setitem__( name, SampleSet(name,samples,parent=self,responses=responses,
                                                indices=indices,index_start=index_start))
        return self.sampleset[name]
    def read_sampleset(self, file, name=None):
        """ Read MATK output file and assemble corresponding sampleset with responses.
        
        :param name: Name of sample set
        :type name: str
        :param file: Path to MATK output file
        :type file: str
        """
        # open file
        if not os.path.isfile(file):
            print 'No file '+file+' found...'
            return
        fp = open(file)
        # parse file
        npar = int(fp.readline().rstrip().split(':')[1])
        nobs = int(fp.readline().rstrip().split(':')[1])
        headers = fp.readline().rstrip().split()
        data = numpy.array([[float(num) for num in line.split()] for line in fp if not line.isspace()])
        indices = numpy.array([int(v) for v in data[:,0]])
        # add parameters
        for header,dat in zip(headers[1:npar+1],data[:,1:npar+1].T):
            if header not in self.pars:
                self.add_par(header,min = numpy.min(dat),max = numpy.max(dat))
        # add observations
        for header in headers[npar+1:]: 
            if header not in self.obs:
                self.add_obs(header)
        # create samples
        samples = data[:,1:npar+1]
        if nobs > 0:
            responses = data[:,npar+1:]
        else: responses = None
        return self.create_sampleset(samples,name=name,responses=responses,indices=indices)
    def copy_sampleset(self,oldname,newname=None):
        """ Copy sampleset

            :param oldname: Name of sampleset to copy
            :type oldname: str
            :param newname: Name of new sampleset
            :type newname: str
        """
        return self.create_sampleset(self.sampleset[oldname].samples.values,name=newname,responses=self.sampleset[oldname].responses.values,indices=self.sampleset[oldname].indices)
    @property
    def simvalues(self):
        """ Simulated values
            :returns: lst(fl64) -- simulated values in order of matk.obs.keys()
        """
        return [obs.sim for obs in self.obs.values()]
    def _set_simvalues(self, *args, **kwargs):
        """ Set simulated values using a tuple, list, numpy.ndarray, dictionary or keyword arguments
        """
        if len(args) > 0 and len(kwargs) > 0:
            print "Warning: dictionary arg will overide keyword args"
        if len(args) > 0:
            if isinstance( args[0], dict ):
                for k,v in args[0].iteritems():
                    if k in self.obs:
                        self.obs[k].sim = v
                    else:
                        self.add_obs( k, sim=v ) 
            elif isinstance( args[0], (list,tuple,numpy.ndarray) ):
                # If no observations exist, create them
                if len(self.obs) == 0:
                    for i,v in zip(range(len(args[0])),args[0]): 
                        self.add_obs('obs'+str(i+1),sim=v)
                elif not len(args[0]) == len(self.obs): 
                    print len(args[0]), len(self.obs)
                    print "Error: Number of simulated values in list or tuple does not match created observations"
                    return
                else:
                    for k,v in zip(self.obs.keys(),args[0]):
                        self.obs[k].sim = v
        else:
            for k,v in kwargs.iteritems():
                if k in self.obs:
                    self.obs[k].sim = v
                else:
                    self.add_obs( k, sim=v ) 
    @property
    def parvalues(self):
        """ Parameter values
        """
        return [par.value for par in self.pars.values()]
    @parvalues.setter
    def parvalues(self, value):
        """ Set parameter values using a tuple, list, numpy.ndarray, or dictionary
        """
        if isinstance( value, dict ):
            for k,v in value.iteritems():
                self.pars[k].value = v
        elif isinstance( value, (list,tuple,numpy.ndarray)):
            if not len(value) == len(self.pars): 
                print "Error: Number of parameter values in ndarray does not match created parameters"
                return
            for v,k in zip(value,self.pars.keys()):
                self.pars[k].value = v
        else:
            print "Error: tuple, list, numpy.ndarray, or dictionary expected"
    @property
    def parnames(self):
        """ Get parameter names
        """
        return [par.name for par in self.pars.values()]
    @property
    def obsvalues(self):
        """ Observation values
        """
        return [o.value for o in self.obs.values()]
    @obsvalues.setter
    def obsvalues(self, value):
        """ Set observed values using a tuple, list, numpy.ndarray, or dictionary
        """
        if isinstance( value, dict ):
            for k,v in value.iteritems():
                if k in self.obs:
                    self.obs[k].value = v
                else:
                    self.add_obs( k, value=v ) 
        elif isinstance( value, (list,tuple,numpy.ndarray) ):
            # If no observations exist, create them
            if len(self.obs) == 0:
                for i,v in enumerate(value): 
                    self.add_obs('obs'+str(i),value=v)
            # else, check if length of value is equal to number created observation
            elif not len(value) == len(self.obs): 
                    print "Error: Number of simulated values does not match created observations"
                    return
            # else, set observation values in order
            else:
                for k,v in zip(self.obs.keys(),value):
                    self.obs[k].value = v
        else:
            print "Error: tuple, list, numpy.ndarray, or dictionary expected"
    @property
    def obsnames(self):
        """ Get observation names
        """
        return [o.name for o in self.obs.values()]
    @property
    def obsweights(self):
        """ Get observation names
        """
        return [o.weight for o in self.obs.values()]
    @property
    def residuals(self):
        """ Get least squares values
        """
        return [o.residual for o in self.obs.values()]
    @property
    def parmins(self):
        """ Get parameter lower bounds
        """
        return [par.min for par in self.pars.values()]
    @property
    def parmaxs(self):
        """ Get parameter lower bounds
        """
        return [par.max for par in self.pars.values()]
    @property
    def pardists(self):
        """ Get parameter probabilistic distributions
        """
        return [par.dist for par in self.pars.values()]
    @property
    def pardist_pars(self):
        """ Get parameters needed by parameter distributions
        """
        return [par.dist_pars for par in self.pars.values()]
    def __iter__(self):
        return self
    def make_workdir(self, workdir=None, reuse_dirs=False):
        """ Create a working directory

            :param workdir: Name of directory where model will be run. It will be created if it does not exist
            :type workdir: str
            :param reuse_dirs: If True and workdir exists, the model will reuse the directory
            :type reuse_dirs: bool
            :returns: int -- 0: Successful run, 1: workdir exists 
        """
        if not workdir is None: self.workdir = workdir
        if not self.workdir is None:
            # If folder doesn't exist
            if not os.path.isdir( self.workdir ):
                os.makedirs( self.workdir )
                return 0
            # or if reusing directories
            elif reuse_dirs:
                pass
                return 0
            # or throw error
            else:
                print "Error: " + self.workdir + " already exists"
                return 1
    def forward(self, pardict=None, workdir=None, reuse_dirs=False, job_number=None, hostname=None, processor=None):
        """ Run MATK model using current values

            :param pardict: Dictionary of parameter values keyed by parameter names
            :type pardict: dict
            :param workdir: Name of directory where model will be run. It will be created if it does not exist
            :type workdir: str
            :param reuse_dirs: If True and workdir exists, the model will reuse the directory
            :type reuse_dirs: bool
            :param job_number: Sample id
            :type job_number: int
            :param hostname: Name of host to run job on, will be passed to MATK model as kwarg 'hostname'
            :type hostname: str
            :param processor: Processor id to run job on, will be passed to MATK model as kwarg 'processor'
            :type processor: str or int
            :returns: int -- 0: Successful run, 1: workdir exists 
        """
        if not workdir is None: self.workdir = workdir
        if not self.workdir is None:
            curdir = os.getcwd()
            status = self.make_workdir( workdir=self.workdir, reuse_dirs=reuse_dirs)
            os.chdir( self.workdir )
            if status:
                return 1
        else:
            curdir = None
        if hasattr( self.model, '__call__' ):
            try:
                if pardict is None:
                    pardict = dict([(k,par.value) for k,par in self.pars.items()])
                else: self.parvalues = pardict
                if self.model_args is None and self.model_kwargs is None:
                    if hostname is None: sims = self.model( pardict )
                    else: 
                        if processor is None: sims = self.model( pardict, hostname=hostname )
                        else: sims = self.model( pardict, hostname=hostname, processor=processor )
                elif not self.model_args is None and self.model_kwargs is None:
                    if hostname is None: sims = self.model( pardict, *self.model_args )
                    else: 
                        if processor is None: sims = self.model( pardict, *self.model_args, hostname=hostname )
                        else: sims = self.model( pardict, *self.model_args, hostname=hostname, processor=processor )
                elif self.model_args is None and not self.model_kwargs is None:
                    if hostname is None: sims = self.model( pardict, **self.model_kwargs )
                    else:
                        if processor is None: sims = self.model( pardict, hostname=hostname, **self.model_kwargs )
                        else: sims = self.model( pardict, hostname=hostname, processor=processor, **self.model_kwargs )
                elif not self.model_args is None and not self.model_kwargs is None:
                    if hostname is None: sims = self.model( pardict, *self.model_args, **self.model_kwargs )
                    else:
                        if processor is None: sims = self.model( pardict, *self.model_args, hostname=hostname, **self.model_kwargs )
                        else: sims = self.model( pardict, *self.model_args, hostname=hostname, processor=processor, **self.model_kwargs )
                self._current = True
                if not curdir is None: os.chdir( curdir )
                if sims is not None:
                    if isinstance(sims,(float,int)): sims = [sims]
                    if len(sims):
                        self._set_simvalues(sims)
                        simdict = OrderedDict(zip(self.obsnames,self.simvalues))
                        return simdict
                else: return None
            except:
                errstr = traceback.format_exc()                
                if not curdir is None: os.chdir( curdir )
                s = "-"*60+'\n'
                if job_number is not None:
                    s += "Exception in job "+str(job_number)+":\n"
                else:
                    s += "Exception in model call:\n"
                s += errstr
                s += "-"*60
                print s
                return s
        else:
            print "Error: Model is not a Python function"
            if not curdir is None: os.chdir( curdir )
            return 1
    def lmfit(self,maxfev=0,report_fit=True,cpus=1,epsfcn=None,xtol=1.e-7,ftol=1.e-7,
              workdir=None, verbose=False, **kwargs):
        """ Calibrate MATK model using lmfit package

            :param maxfev: Max number of function evaluations, if 0, 100*(npars+1) will be used
            :type maxfev: int
            :param report_fit: If True, parameter statistics and correlations are printed to the screen
            :type report_fit: bool
            :param cpus: Number of cpus to use for concurrent simulations during jacobian approximation
            :type cpus: int
            :param epsfcn: jacobian finite difference approximation increment (single float of list of npar floats)
            :type epsfcn: float or lst[float]
            :param xtol: Relative error in approximate solution
            :type xtol: float
            :param ftol: Relative error in the desired sum of squares
            :type ftol: float
            :param workdir: Name of directory to use for model runs, calibrated parameters will be run there after calibration 
            :type workdir: str
            :param verbose: If true, print diagnostic information to the screen
            :type verbose: bool
            :returns: lmfit minimizer object

            Additional keyword argments will be passed to scipy leastsq function:
            http://docs.scipy.org/doc/scipy-0.15.1/reference/generated/scipy.optimize.leastsq.html
        """
           
        try: import lmfit
        except ImportError as exc:
            sys.stderr.write("Warning: failed to import lmfit module. ({})".format(exc))
            return
        self.cpus = cpus

        # Create lmfit parameter object
        params = lmfit.Parameters()
        for k,p in self.pars.items():
            params.add(k,value=p.value,vary=p.vary,min=p.min,max=p.max,expr=p.expr) 

        out = lmfit.minimize(self.__lmfit_residual, params, args=(cpus,epsfcn,workdir,verbose), 
                maxfev=maxfev,xtol=xtol,ftol=ftol,Dfun=self.__jacobian, **kwargs)

        # Make sure that self.pars are set to final values of params
        nm = [params[k].name for k in self.pars.keys()]
        vs = [params[k].value for k in self.pars.keys()]
        self.parvalues = dict(zip(nm,vs))
        # Run forward model to set simulated values
        if isinstance( cpus, int):
            self.forward(workdir=workdir,reuse_dirs=True)
        elif isinstance( cpus, dict):
            hostname = cpus.keys()[0]
            processor = cpus[hostname][0]
            self.forward(workdir=workdir,reuse_dirs=True,
                         hostname=hostname,processor=processor)
        else:
            print 'Error: cpus argument type not recognized'
            return

        if report_fit:
            print lmfit.report_fit(params)
            print 'SSR: ',self.ssr
        return out
    def __lmfit_residual(self, params, cpus=1, epsfcn=None, workdir=None,verbose=False,save=False):
        if verbose: print 'forward run: ',params
        pardict = dict([(k,n.value) for k,n in params.items()])
        if isinstance( cpus, int):
            self.forward(pardict=pardict,workdir=workdir,reuse_dirs=True)
        elif isinstance( cpus, dict):
            hostname = cpus.keys()[0]
            processor = cpus[hostname][0]
            self.forward(pardict=pardict,workdir=workdir,reuse_dirs=True,
                         hostname=hostname,processor=processor)
        else:
            print 'Error: cpus argument type not recognized'
            return
        if verbose: print 'SSR: ', numpy.sum([v**2 for v in self.residuals])
        return self.residuals
    def __jacobian( self, params, cpus=1, epsfcn=None, workdir_base=None,verbose=False,save=False,
                   reuse_dirs=True):
        ''' Numerical Jacobian calculation
        '''
        # Collect parameter values
        a = numpy.array([k.value for k in params.values()])
        # Determine finite difference increment for each parameter
        if epsfcn is None:
            hs = numpy.sqrt(numpy.finfo(float).eps)*a
            hs[numpy.where(hs==0)[0]] = numpy.sqrt(numpy.finfo(float).eps)
        elif isinstance(epsfcn,float):
            hs = epsfcn * numpy.ones(len(a))
        else:
            hs = numpy.array(epsfcn)
        # Forward differences
        humat = numpy.identity(len(a))*hs
        parset = [a]*humat.shape[0] + humat
        parset = numpy.append(parset,[a],axis=0)
        self.create_sampleset(parset,name='_jac_')

        # Perform simulations on parameter sets
        self.sampleset['_jac_'].run( cpus=cpus, verbose=False,
                         workdir_base=workdir_base, save=False, reuse_dirs=reuse_dirs )
        sims = self.sampleset['_jac_'].responses.values
        diffsims = sims[:len(a)]
        zerosims = sims[-1]
        ##print 'diffsims: ', diffsims, diffsims.shape
        #print 'zerosims: ', zerosims, zerosims.shape
        J = []
        for h,d in zip(hs,diffsims):
            J.append((zerosims-d)/h)
        self.parvalues = a
        return numpy.array(J).T

    def levmar(self,workdir=None,reuse_dirs=False,max_iter=1000,full_output=True):
        """ Calibrate MATK model using levmar package

            :param workdir: Name of directory where model will be run. It will be created if it does not exist
            :type workdir: str
            :param reuse_dirs: If True and workdir exists, the model will reuse the directory
            :type reuse_dirs: bool
            :param max_iter: Maximum number of iterations
            :type max_iter: int
            :param full_output: If True, additional output displayed during calibration
            :returns: levmar output
        """
        try: import levmar
        except ImportError as exc:
            sys.stderr.write("Warning: failed to import levmar module. ({})".format(exc))
            return
        def _f(pars, prob):
            prob = prob[0]
            nm = [p.name for p in prob.pars.values()]
            vs = [p._func_value(v) for v,p in zip(pars,prob.pars.values())]
            print nm,vs
            prob.forward(pardict=dict(zip(nm,vs)),workdir=workdir,reuse_dirs=reuse_dirs)
            return prob.simvalues
        vs = [p.from_internal for p in self.pars.values()]
        meas = self.obsvalues
        if full_output: full_output = 1
        out = levmar.leastsq(_f, vs, meas, args=(self,), Dfun=None, max_iter=max_iter, full_output=full_output)
        #TODO Put levmar results into MATK object
        return out
    def lhs(self, name=None, siz=None, noCorrRestr=False, corrmat=None, seed=None, index_start=1):
        """ Draw lhs samples of parameter values from scipy.stats module distribution
        
            :param name: Name of sample set to be created
            :type name: str
            :param siz: Number of samples to generate, ignored if samples are provided
            :type siz: int
            :param noCorrRestr: If True, correlation structure is not enforced on sample, use if siz is less than number of parameters
            :type noCorrRestr: bool
            :param corrmat: Correlation matrix
            :type corrmat: matrix
            :param seed: Random seed to allow replication of samples
            :type seed: int
            :param index_start: Starting value for sample indices
            :type: int
            :returns: matrix -- Parameter samples
          
        """
        if seed:
            self.seed = seed
        # If siz specified, set sample_size
        if siz:
            self.sample_size = siz
        else:
            siz = self.sample_size
        # Take distribution keyword and convert to scipy.stats distribution object
        dists = []
        for dist in self.pardists:
            eval( 'dists.append(stats.' + dist + ')' )
        dist_pars = self.pardist_pars
        x = lhs(dists, dist_pars, siz=siz, noCorrRestr=noCorrRestr, corrmat=corrmat, seed=seed)
        for j,p in enumerate(self.pars.values()):
            if p.expr is not None:
                for i,r in enumerate(x):
                    x[i,j] = self.__eval_expr( p.expr, r )
        return self.create_sampleset( x, name=name, index_start=index_start )
    def child( self, in_queue, out_list, reuse_dirs, save, hostname, processor):
        for pars,smp_ind,lst_ind in iter(in_queue.get, ('','','')):
            self.workdir_index = smp_ind
            if self.workdir_base is not None:
                self.workdir = self.workdir_base + '.' + str(self.workdir_index)
            self.parvalues = pars
            status = self.forward(reuse_dirs=reuse_dirs, job_number=smp_ind, hostname=hostname, processor=processor)
            out_list.put([lst_ind, smp_ind, status])
            if not save and not self.workdir is None:
                rmtree( self.workdir )
            in_queue.task_done()
        in_queue.task_done()
    def parallel(self, parsets, cpus=1, workdir_base=None, save=True,
                reuse_dirs=False, indices=None, verbose=True, logfile=None):

        if not os.name is "posix":
            # Use freeze_support for PCs
            freeze_support()

        # Determine if using working directories or not
        saved_workdir = self.workdir # Save workdir to reset after parallel run
        if not workdir_base is None: self.workdir_base = workdir_base
        if self.workdir_base is None: self.workdir = None

        #if len(hosts) > 0:
        if isinstance( cpus, dict):
            hosts = cpus
            cpus = sum([len(v) for v in hosts.values()])
            processors = [v for l in hosts.values() for v in l]
            hostnames = [k for k,v in hosts.items() for n in v]
            self.cpus = hosts
        elif isinstance(self.cpus,dict) and len(self.cpus) > 0:
            hosts = self.cpus
            cpus = sum([len(v) for v in hosts.values()])
            processors = [v for l in hosts.values() for v in l]
            hostnames = [k for k,v in hosts.items() for n in v]
        elif isinstance(cpus, int):
            hostnames = [None]*cpus
            processors = [None]*cpus
        else:
            print "Error: cpus argument is neither an integer nor a dictionary!"
            return

        # Determine number of samples and adjust cpus if samples < cpus requested
        if isinstance( parsets, numpy.ndarray ): n = parsets.shape[0]
        elif isinstance( parsets, list ): n = len(parsets)
        if n < cpus: cpus = n

        # Start cpus model runs
        resultsq = Queue()
        work = JoinableQueue()
        pool = []
        for i in range(cpus):
            p = Process(target=self.child, args=(work, resultsq, reuse_dirs, save, hostnames[i],processors[i]))
            p.daemon = True
            p.start()
            pool.append(p)

        iter_args = itertools.chain( parsets, ('',)*cpus )
        iter_smpind = itertools.chain( indices, ('',)*cpus )
        iter_lstind = itertools.chain( range(len(parsets)), ('',)*cpus )
        for item in zip(iter_args,iter_smpind,iter_lstind):
            work.put(item)
        
        if verbose or logfile: 
            if logfile: f = open(logfile, 'w')
            s = "%-8s" % 'index'
            for nm in self.parnames:
                s += " %16s" % nm
            header = True

        results = [[numpy.NAN]]*len(parsets)
        for i in range(len(parsets)):
            lst_ind, smp_ind, resp = resultsq.get()
            if isinstance( resp, str):
                if logfile: 
                    f.write(resp+'\n')
                    f.flush()
            else:
                if isinstance( resp, OrderedDict):
                    self._set_simvalues(resp)
                    results[lst_ind] = resp.values()
                if verbose or logfile:
                    if header:
                        for nm in self.obsnames:
                            s += " %16s" % nm
                        s += '\n'
                        if verbose: print s,
                        if logfile: 
                            f.write( s )
                            f.flush()
                        header = False
                    s = "%-8d" % smp_ind
                    for v in parsets[lst_ind]:
                        s += " %16lf" % v
                    if results[lst_ind] is not numpy.NAN:
                        for v in results[lst_ind]:
                            s += " %16lf" % v
                    s += '\n'
                    if verbose: print s,
                    if logfile: 
                        f.write( s )
                        f.flush()
        if logfile: f.close()

        for i in range(len(results)):
            if results[i] is numpy.NAN:
                if len(self.obs) > 0:
                    results[i] = [numpy.NAN]*len(self.obs)

        for p in pool:
            p.join()

        # Clean parent
        self.workdir = saved_workdir
        results = numpy.array(results)
        if results.shape[1] == 1:
            if all(numpy.isnan(r[0]) for r in results):
                results = None

        return results, parsets   
    def parstudy(self, name=None, nvals=2):
        ''' Generate parameter study samples
        
        :param name: Name of sample set to be created
        :type name: str
        :param outfile: Name of file where samples will be written. If outfile=None, no file is written.
        :type outfile: str
        :param nvals: number of values for each parameter
        :type nvals: int or list(int)
        :returns: ndarray(fl64) -- Array of samples
        '''

        if isinstance(nvals,int):
            nvals = [nvals]*len(self.pars)
        x = []
        for p,n in zip(self.pars.values(),nvals):
            if n == 1 or not p.vary:
                x.append(numpy.linspace(p.value, p.max, n))
            elif n > 1:
                x.append(numpy.linspace(p.min, p.max, n))

        x = list(itertools.product(*x))
        x = numpy.array(x)

        return self.create_sampleset( x, name=name )
    def fullfact(self,name=None,levels=[]):
        try:
            import pyDOE
        except ImportError as exc:
            sys.stderr.write("Warning: failed to import pyDOE module. ({})".format(exc))
            return
        if len(levels) == 0:
            levels = numpy.array([p.nvals for p in self.pars.values()])
        elif len(levels) != len(self.pars): 
            print "Error: Length of levels ("+str(len(levels))+") not equal to number of parameters ("+str(len(self.pars))+")"
            return
        else:
            levels = numpy.array(levels)
        ds = pyDOE.fullfact(levels)
        mns = numpy.array(self.parmins)
        mxs = numpy.array(self.parmaxs)
        parsets = mns + ds/(levels-1)*(mxs-mns)
        return self.create_sampleset(parsets, name=name)
    def Jac( self, h=None, cpus=1, workdir_base=None,
                    save=True, reuse_dirs=False, verbose=False ):
        ''' Numerical Jacobian calculation

            :param h: Parameter increment, single value or array with npar values
            :type h: fl64 or ndarray(fl64)
            :returns: ndarray(fl64) -- Jacobian matrix
        '''
        try: import lmfit
        except ImportError as exc:
            sys.stderr.write("Warning: failed to import lmfit module. ({})".format(exc))
            return

        # Create lmfit parameter object
        params = lmfit.Parameters()
        for k,p in self.pars.items():
            params.add(k,value=p.value,vary=p.vary,min=p.min,max=p.max,expr=p.expr) 

        return self.__jacobian( params, cpus=cpus, epsfcn=h, workdir_base=workdir_base,verbose=verbose,save=save, reuse_dirs=reuse_dirs)

    def calibrate( self, cpus=1, maxiter=100, lambdax=0.001, minchange=1.0e-16, minlambdax=1.0e-6, verbose=False,
                  workdir=None, reuse_dirs=False, h=1.e-6):
        """ Calibrate MATK model using Levenberg-Marquardt algorithm based on 
            original code written by Ernesto P. Adorio PhD. 
            (UPDEPP at Clarkfield, Pampanga)

            :param cpus: Number of cpus to use
            :type cpus: int
            :param maxiter: Maximum number of iterations
            :type maxiter: int
            :param lambdax: Initial Marquardt lambda
            :type lambdax: fl64
            :param minchange: Minimum change between successive ChiSquares
            :type minchange: fl64
            :param minlambdax: Minimum lambda value
            :type minlambdax: fl4
            :param verbose: If True, additional information written to screen during calibration
            :type verbose: bool
            :returns: best fit parameters found by routine
            :returns: best Sum of squares.
            :returns: covariance matrix
        """
        from minimizer import Minimizer
        fitter = Minimizer(self)
        fitter.calibrate(cpus=cpus,maxiter=maxiter,lambdax=lambdax,minchange=minchange,
                         minlambdax=minlambdax,verbose=verbose,workdir=workdir,reuse_dirs=reuse_dirs,h=h)
    def __eval_expr(self, exprstr, parset):
        aeval = Interpreter()
        for val,nm in zip(parset,self.pars.keys()):
            aeval.symtable[nm] = val
        return aeval(exprstr)
    def MCMC( self, nruns=10000, burn=1000, init_error_std=1., max_error_std=100., verbose=1 ):
        ''' Perform Markov Chain Monte Carlo sampling using pymc package

            :param nruns: Number of MCMC iterations (samples)
            :type nruns: int
            :param burn: Number of initial samples to burn (discard)
            :type burn: int
            :param verbose: verbosity of output
            :type verbose: int
            :param init_error_std: Initial standard deviation of residuals
            :type init_error_std: fl64
            :param max_error_std: Maximum standard deviation of residuals that will be considered
            :type max_error_std: fl64
            :returns: pymc MCMC object
        '''
        if max_error_std < init_error_std:
            print "Error: max_error_std must be greater than or equal to init_error_std"
            return
        try:
            from pymc import Uniform, deterministic, Normal, MCMC, Matplot
        except ImportError as exc:
            sys.stderr.write("Warning: failed to import pymc module. ({})\n".format(exc))
            sys.stderr.write("If pymc is not installed, try installing:\n")
            sys.stderr.write("e.g. try using easy_install: easy_install pymc\n")
        def __mcmc_model( self, init_error_std=1., max_error_std=100. ):
            #priors
            variables = []
            sig = Uniform('error_std', 0.0, max_error_std, value=init_error_std)
            variables.append( sig )
            for nm,mn,mx in zip(self.parnames,self.parmins,self.parmaxs):
                evalstr = "Uniform( '" + str(nm) + "', " +  str(mn) + ", " +  str(mx) + ")"
                variables.append( eval(evalstr) )
            #model
            @deterministic()
            def residuals( pars = variables, p=self ):
                values = []
                for i in range(1,len(pars)):
                    values.append(float(pars[i]))
                pardict = dict(zip(p.parnames,values))
                p.forward(pardict=pardict, reuse_dirs=True)
                return numpy.array(p.residuals)*numpy.array(p.obsweights)
            #likelihood
            y = Normal('y', mu=residuals, tau=1.0/sig**2, observed=True, value=numpy.zeros(len(self.obs)))
            variables.append(y)
            return variables

        M = MCMC( __mcmc_model(self, init_error_std=init_error_std, max_error_std=max_error_std) )
        M.sample(iter=nruns,burn=burn,verbose=verbose)
        return M
    def MCMCplot( self, M ):
        try:
            from pymc import Uniform, deterministic, Normal, MCMC, Matplot
        except ImportError as exc:
            sys.stderr.write("Warning: failed to import pymc module. ({})\n".format(exc))
            sys.stderr.write("If pymc is not installed, try installing:\n")
            sys.stderr.write("e.g. try using easy_install: easy_install pymc\n")
        Matplot.plot(M)
    def emcee( self, lnprob=None, nwalkers=100, nsamples=500, burnin=50, pos0=None ):
        ''' Perform Markov Chain Monte Carlo sampling using emcee package

            :param lnprob: Function specifying the natural logarithm of the likelihood function
            :type lnprob: function
            :param nwalkers: Number of random walkers
            :type nwalkers: int
            :param nsamples: Number of samples per walker
            :type nsamples: int
            :param burnin: Number of "burn-in" samples per walker to be discarded
            :type burnin: int
            :param pos0: list of initial positions for the walkers
            :type pos0: list
            :returns: numpy array containing samples
        '''
        try:
            import emcee
        except ImportError as exc:
            sys.stderr.write("Warning: failed to import emcee module. ({})\n".format(exc))
        if lnprob is None:
            lnprob = logposterior(self)
        sampler = emcee.EnsembleSampler(nwalkers, len(self.parnames), lnprob, threads=self.cpus)
        if pos0 == None:
            try:
                from pyDOE import lhs
                lh = lhs(len(self.parnames), samples=nwalkers)
                pos0 = []
                for i in range(nwalkers):
                    pos0.append([pmin + (pmax - pmin) * lhval for lhval, pmin, pmax in zip(lh[i], self.parmins, self.parmaxs)])
            except ImportError as exc:
                sys.stderr.write("Warning: failed to import pyDOE module. ({})\n".format(exc))
        sampler.run_mcmc(pos0, nsamples)
        return sampler.chain[:, burnin:, :].reshape((-1, len(self.parnames)))

class logposterior(object):
    def __init__(self, prob, var=1):
        self.prob = prob
        self.mins = prob.parmins
        self.maxs = prob.parmaxs
        self.var = var
    def logprior(self,ts):
        for mn,mx,t in zip(self.mins,self.maxs,ts):
            if mn > t or t > mx: return -numpy.inf 
        return 0.0
    def loglhood(self,ts):
        pardict = dict(zip(self.prob.parnames, ts))
        self.prob.forward(pardict=pardict, reuse_dirs=True)
        return -0.5*(numpy.sum((numpy.array(self.prob.residuals))**2)) / self.var - numpy.log(self.var)
    def __call__(self, ts):
        lpri = self.logprior(ts)
        if lpri == -numpy.inf:
            return lpri
        else:
            return lpri + self.loglhood(ts)

class logposteriorwithvariance(logposterior):
    def __init__(self, prob, var="var"):
        self.prob = prob
        self.mins = prob.parmins
        self.maxs = prob.parmaxs
        self.var = var
    def loglhood(self,ts):
        pardict = dict(zip(self.prob.parnames, ts))
        self.prob.forward(pardict=pardict, reuse_dirs=True)
        #print "ts: " + str(ts)
        #print "ssr: " + str(numpy.sum((numpy.array(self.prob.residuals))**2))
        #print zip(self.prob.simvalues, self.prob.obsvalues)
        #return -0.5*(numpy.sum((numpy.array(self.prob.residuals))**2)) / self.prob.pars[self.var].value - numpy.log(self.prob.pars[self.var].value)
        return -0.5*(numpy.sum((numpy.array(self.prob.residuals))**2)) / self.prob.pars[self.var].value - (len(self.prob.obs)/2)*numpy.log(self.prob.pars[self.var].value)

