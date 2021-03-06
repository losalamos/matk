import sys
import numpy
import string
from scipy import stats
from shutil import rmtree
from operator import itemgetter
try:
    from matplotlib import pyplot as plt
    from matplotlib.ticker import MaxNLocator
    from matplotlib import rc as mplrc
    plotflag = True
except ImportError as exc:
    sys.stderr.write("Warning: failed to import matplotlib module. Plots will not be produced. ({})".format(exc))
    plotflag = False
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

class SampleSet(object):
    """ MATK SampleSet class - Stores information related to a sample
        including parameter samples, associated responses, and sample indices
    """
    def __init__(self,name,samples,parent,index_start=1,**kwargs):
        self.name = name
        responses = None
        self._indices = None
        self._index_start = index_start
        self._parent = parent
        self.samples = DataSet(samples,self._parent.parnames,mins=self._parent.parmins,maxs=self._parent.parmaxs) 
        for k,v in kwargs.iteritems():
            if k == 'responses':
                if not v is None:
                    if isinstance( v, (list,numpy.ndarray)):
                       responses = numpy.array(v)
                    else:
                        print "Error: Responses are not a list or ndarray"
                        return
            elif k == 'indices':
                if not v is None:
                    if isinstance( v, (list,numpy.ndarray)):
                        self.indices = v
                    else:
                        print "Error: Indices are not a list or ndarray"
                        return
        if self._parent.obsnames is None and responses is not None:
            self._parent._obsnames = []
            for i in range(responses.shape[0]):
                self._parent._obsnames.append('obs'+str(i))
        if responses is not None:
            self.responses = DataSet(responses,self._parent.obsnames) 
        else:
            self.responses = None
        # Set default indices if None
        if self.indices is None and not self.samples.values is None:
            if not self.index_start is None:
                self.indices = numpy.arange(index_start,index_start+self.samples.values.shape[0])
            else:
                self.indices = numpy.arange(self.samples.values.shape[0])+1
    @property
    def name(self):
        """Sample set name
        """
        return self._name
    @name.setter
    def name(self,value):
        self._name = value
    @property
    def indices(self):
        """ Array of sample indices
        """ 
        return self._indices
    @indices.setter
    def indices(self,value):
        if self.samples is None and value is None:
            self._indices = value
        elif self.samples is None and not value is None:
            print "Error: Samples are not defined"
            return
        elif value is None:
            self._indices = value
        elif not len(value) == self.samples.values.shape[0]:
            print "Error: number of indices does not equal number of samples"
            return
        else:
            self._indices = value
    @property
    def parnames(self):
        """ Array of observation names
        """ 
        if not self._parent is None:
            if len(self._parent.parnames):
                self._parnames = self._parent.parnames
        return self._parnames
    @property
    def obsnames(self):
        """ Array of observation names
        """ 
        if not self._parent is None:
            if len(self._parent.obsnames):
                self._obsnames = self._parent.obsnames
        return self._obsnames
    @property
    def index_start(self):
        """ Starting integer value for sample indices
        """
        return self._index_start
    @index_start.setter
    def index_start(self,value):
        if not isinstance( value, int):
            print "Error: Expecting integer"
            return
        self._index_start = value
        if not self.samples is None:
            self.indices = numpy.arange(self.index_start,self.index_start+self.samples.values.shape[0])
    @property
    def recarray(self):
        """ Structured (record) array of samples
        """
        if self.responses is None:
            return numpy.rec.fromarrays(self.samples._values.T,names=self.samples._names)
        else:
            data = numpy.column_stack([self.samples._values,self.responses._values])
            names = numpy.concatenate([self.samples._names,self.responses._names])
            return numpy.rec.fromarrays(data.T,names=names.tolist())
    def pardict(self, index):
        """ Get parameter dictionary for sample with specified index

            :param index: Sample index
            :type index: int
            :returns: dict(fl64)
        """
        try:
            row_index = numpy.where(self.indices==index)[0][0]
        except:
            print "\nIndex not found"
            return
        return OrderedDict(zip(self.parnames,self.samples.values[row_index]))
    def calc_sse(self):
        """ Calculate sum of squared errors (sse) for all samples

            :return: lst(fl64)
        """
        if len(self._parent.obsvalues) == 0:
            print "Observations are not set (e.g. prob.obsvalues is empty)"
            return 0
        elif self.responses is None:
            print "Responses have not been calculated. Run sampleset (e.g. sampleset.run())"
            return 0
        self.sse = [numpy.sum((self._parent.obsvalues - self.responses.values[i,:])**2) for i in range(len(self.responses.values))]
        return self.sse
    def corr(self, type='pearson', plot=False, printout=True, plotvals=True, figsize=None, title=None):
        """ Calculate correlation coefficients of parameters and responses

            :param type: Type of correlation coefficient (pearson by default, spearman also avaialable)
            :type type: str
            :param plot: If True, plot correlation matrix
            :type plot: bool
            :param printout: If True, print correlation matrix with row and column headings
            :type printout: bool
            :param plotvals: If True, print correlation coefficients on plot matrix
            :type plotvals: bool
            :param figsize: Width and height of figure in inches
            :type figsize: tuple(fl64,fl64)
            :param title: Title of plot
            :type title: str
            :returns: ndarray(fl64) -- Correlation coefficients
        """
        corrcoef = corr(self.samples.recarray, self.responses.recarray, type=type, plot=plot, printout=printout, plotvals=plotvals, figsize=figsize, title=title)
        return corrcoef
    
    def panels(self, type='pearson', alpha=0.2, figsize=None, title=None, tight=False, symbol='.',fontsize=None,corrfontsize=None,ms=5,mins=None,maxs=None,frequency=False,bins=10, ylim=None, labels=[], filename=None, xticks=2, yticks=2):
        """ Plot histograms, scatterplots, and correlation coefficients in paired matrix

            :param type: Type of correlation coefficient (pearson by default, spearman also avaialable)
            :type type: str
            :param alpha: Histogram color shading
            :type alpha: float
            :param figsize: Width and height of figure in inches
            :type figsize: tuple(fl64,fl64)
            :param title: Title of plot
            :type title: str
            :param tight: Use matplotlib tight layout
            :type tight: bool
            :param symbol: matplotlib symbol for scatterplots
            :type symbol: str
            :param fontsize: Size of font for axis labels
            :type fontsize: fl64
            :param corrfontsize: Size of font for correlation coefficients
            :type corrfontsize: fl64
            :param ms: Scatterplot marker size
            :type ms: fl64
            :param frequency: If True, the first element of the return tuple will be the counts normalized by the length of data, i.e., n/len(x)
            :type frequency: bool
            :param bins: Number of bins in histograms
            :type bins: int
            :param ylim: y-axis limits for histograms.
            :type ylim: tuples - 2 element tuples with y limits for histograms
            :param labels: Names to use instead of parameter names in plot
            :type labels: lst(str)
            :param filename: Name of file to save plot. File ending determines plot type (pdf, png, ps, eps, etc.). Plot types available depends on the matplotlib backend in use on the system. Plot will not be displayed.
            :type filename: str
            :param xticks: Number of ticks along x axes 
            :type filename: int
            :param yticks: Number of ticks along y axes 
            :type filename: int
        """
        if self.responses is None:
            if mins is None and self.samples._mins is not None: mins = self.samples._mins
            if maxs is None and self.samples._maxs is not None: maxs = self.samples._maxs
        else:
            if mins is None and self.samples._mins is not None: mins = numpy.concatenate([self.samples._mins,numpy.min(self.responses.values,axis=0)])
            if maxs is None and self.samples._maxs is not None: maxs = numpy.concatenate([self.samples._maxs,numpy.max(self.responses.values,axis=0)])
        panels( self.recarray, type=type, alpha=alpha, figsize=figsize, title=title, tight=tight, symbol=symbol,fontsize=fontsize,corrfontsize=corrfontsize,ms=ms,mins=mins,maxs=maxs,frequency=frequency,bins=bins,ylim=ylim,labels=labels,filename=filename,xticks=xticks,yticks=yticks)
    def run(self, cpus=1, workdir_base=None, save=True, reuse_dirs=False, outfile=None, 
            logfile=None, verbose=True, hosts={} ):
        """ Run model using values in samples for parameter values
            If samples are not specified, LHS samples are produced
            
            :param cpus: number of cpus; alternatively, dictionary of lists of processor ids keyed by hostnames to run models on (i.e. on a cluster); hostname provided as kwarg to model (hostname=<hostname>); processor id provided as kwarg to model (processor=<processor id>)
            :type cpus: int,dict(lst)
            :param workdir_base: Base name for model run folders, run index is appended to workdir_base
            :type workdir_base: str
            :param save: If True, model files and folders will not be deleted during parallel model execution
            :type save: bool
            :param reuse_dirs: Will use existing directories if True, will return an error if False and directory exists
            :type reuse_dirs: bool
            :param outfile: File to write results to
            :type outfile: str
            :param logfile: File to write details of run to during execution
            :type logfile: str
            :param hosts: Option deprecated, use cpus instead
            :type hosts: lst(str)
            :returns: tuple(ndarray(fl64),ndarray(fl64)) - (Matrix of responses from sampled model runs siz rows by npar columns, Parameter samples, same as input samples if provided)
        """
        if workdir_base:
            self._parent.workdir_base = workdir_base

        if len(hosts) > 0:
            print "Error: host option deprecated, use cpus instead. cpus accepts an integer or dictionary of lists of processor ids keyed by hostnames in the same way that the hosts argument functioned"
            return
                
        if cpus > 0:
            out, samples = self._parent.parallel(self.samples.values, cpus, 
                 indices=self.indices, workdir_base=workdir_base, 
                 save=save, reuse_dirs=reuse_dirs, verbose=verbose, logfile=logfile)
        else:
            print 'Error: number of cpus must be greater than zero'
            return
        if out is not None:
            out = numpy.array(out)
            if self.responses is None:
                self.responses = DataSet(out,self._parent.obsnames) 
            else:
                self.responses.values = out 
            self._obsnames = self._parent.obsnames
        if not outfile is None:
            self.savetxt( outfile )

        return out
    def copy(self, newname=None):
        return self._parent.copy_sampleset(self.name,newname=newname)
    def savetxt( self, outfile):
        ''' Save sampleset to file

            :param outfile: Name of file where sampleset will be written
            :type outfile: str
        '''

        x = numpy.column_stack([self.indices,self.samples.values])
        if not self.responses is None:
            x = numpy.column_stack([x,self.responses.values])

        if outfile:
            f = open(outfile, 'w')
            f.write("Number of parameters: %d\n" % len(self.parnames) )
            if not self.responses is None:
                f.write("Number of responses: %d\n" % len(self.obsnames) )
            else: f.write("Number of responses: %d\n" % 0 ) 
            f.write("%-8s" % 'index' )
            # Print par names
            for nm in self.samples.names:
                f.write(" %16s" % nm )
            # Print obs names if responses exist
            if not self.responses is None:
                if len(self.obsnames) == 0:
                    for i in range(self.responses.values.shape[1]):
                        f.write("%16s" % 'obs'+str(i+1) )
                else:
                    for nm in self.obsnames:
                        f.write(" %16s" % nm )
            f.write('\n')
            for row in x:
                if isinstance( row[0], str ):
                    f.write("%-8s" % row[0] )
                else:
                    f.write("%-8d" % row[0] )
                for i in range(1,len(row)):
                    if isinstance( row[i], str):
                        f.write(" %16s" % row[i] )
                    else:
                        f.write(" %16g" % row[i] )
                f.write('\n')
            f.close()
    def subset(self, boolfcn, obs, *args, **kwargs): 
        """ Collect samples based on response values, remove all others

            :param boofcn: Function that returns true for samples to keep and false for samples to remove
            :type boolfcn: function handle
            :param obs: Name of response to apply boolfcn to
            :type obs: str
            :param args: Additional arguments to add to boolfcn
            :param kwargs: Keyword arguments to add to boolfcn 
        """
        if self.responses is None:
            print 'Error: sampleset contains no responses'
            return
        inds = []
        boolarr = numpy.array([boolfcn(val,*args,**kwargs) for val in self.responses.recarray[obs]])
        inds = numpy.where(boolarr)[0]
        if len(inds):
            self.samples._values = self.samples._values[inds.tolist(),:]
            self.responses._values = self.responses._values[inds.tolist(),:]
            self.indices = self.indices[inds.tolist()]
    def main_effects(self):
        """ For each parameter, compile array of main effects.
        """
        # checks
        N = len(self._parent.pars.keys())
        if self.samples._values.shape[0] != 2**N:
            print 'Expecting 2**N samples where N = number of parameters'
            return None, None, None
        # sort lists by parameter value            
        sorted_samples = [[i]+list(s) for i,s in enumerate(self.samples._values)]
        for i in range(N,0,-1): sorted_samples.sort(key = itemgetter(i))
        # for each parameter
        pairDict = []
        for i,parname in zip(range(N-1,-1,-1),self._parent.pars.keys()):             
            inds = range(0,2**N+1,2**i)
            # for each parameter pairing set
            pairs = []
            for j in range(1,(len(inds)-1)/2+1):
                set1 = sorted_samples[inds[2*(j-1)]:inds[2*j-1]]
                set2 = sorted_samples[inds[2*j-1]:inds[2*j]]
                # for each parameter pair
                for s1,s2 in zip(set1,set2):
                    pairs.append((s1[0],s2[0]))
            pairDict.append((parname,pairs))
        pairDict = dict(pairDict)
        # for each observation - parameter pair set, calculate the set of sensitivities
        sensitivity_matrix = []
        for i,obs in enumerate(self._parent.obs.keys()):
            row = []
            for par in self._parent.pars.keys():
                deltas = []
                for pair in pairDict[par]:
                    deltas.append(self.responses.values[pair[1],i]-self.responses.values[pair[0],i])
                row.append(deltas)
            sensitivity_matrix.append(row)
        # calculate matrices of mean and variance sensitivities
        mean_matrix = []
        var_matrix = []
        for row in sensitivity_matrix:
            mean_row = []
            var_row = []
            for col in row:
                mean_row.append(numpy.mean(col))
                var_row.append(numpy.std(col)**2)
            mean_matrix.append(mean_row)
            var_matrix.append(var_row)
            
        return sensitivity_matrix, mean_matrix, var_matrix
    def rank_parameter_frequencies(self):
        """ Yields a printout of parameter value frequencies in the sample set
        
        returns An array of tuples, each containing the parameter name tagged as min or max and a
            second tuple containing the parameter value and the frequency of its appearance in the sample set.
        """
        # create dictionary of parameter name and value
        pars = []
        for par,col in zip(self._parent.pars,self.samples._values.T):
            min = self._parent.pars[par].min
            max = self._parent.pars[par].max
            minN = list(col).count(min)
            maxN = list(col).count(max)
            pars.append((par+':min',[min,minN]))
            pars.append((par+':max',[max,maxN]))
        
        pars.sort(key=lambda x: x[1][1],reverse=True)
            
        return pars
            
class DataSet(object):
    """ MATK Samples class
    """
    def __init__(self,samples,names,mins=None,maxs=None):
        self._values = samples
        self._names = names
        if mins is None: self._mins = [None]*self._values.shape[1]
        else: self._mins = mins
        if maxs is None: self._maxs = [None]*self._values.shape[1]
        else: self._maxs = maxs
    @property
    def names(self):
        """ Array of parameter names
        """ 
        return self._names
    @property
    def values(self):
        """Ndarray of parameter samples, rows are samples, columns are parameters in order of MATKobject.parlist
        """
        return self._values
    @values.setter
    def values(self,value):
        if not isinstance( value, (list,numpy.ndarray)):
            print "Error: Parameter samples are not a list or ndarray"
            return
        # If list, convert to ndarray
        if isinstance( value, list ):
            self._values = numpy.array(value)
        else:
            self._values = value
    @property
    def recarray(self):
        """ Structured (record) array of samples
        """
        return numpy.rec.fromarrays(self._values.T,names=self._names)
    def hist(self, ncols=4, alpha=0.2, figsize=None, title=None, tight=False, mins=None, maxs=None,frequency=False,bins=10,ylim=None,printout=True,labels=[],filename=None,fontsize=None,xticks=3):
        """ Plot histograms of dataset

            :param ncols: Number of columns in plot matrix
            :type ncols: int
            :param alpha: Histogram color shading
            :type alpha: float
            :param figsize: Width and height of figure in inches
            :type figsize: tuple(fl64,fl64)
            :param title: Title of plot
            :type title: str
            :param tight: Use matplotlib tight layout
            :type tight: bool
            :returns: dict(lst(int),lst(fl64)) - dictionary of histogram data (counts,bins) keyed by name
            :param frequency: If True, the first element of the return tuple will be the counts normalized by the length of data, i.e., n/len(x)
            :type frequency: bool
            :param bins: Number of bins in histograms
            :type bins: int
            :param ylim: y-axis limits for histograms.
            :type ylim: tuple - 2 element tuple with y limits for histograms
            :param printout: If True, histogram values are printed to the terminal
            :type printout: bool
            :param labels: Names to use instead of parameter names in plot
            :type labels: lst(str)
            :param filename: Name of file to save plot. File ending determines plot type (pdf, png, ps, eps, etc.). Plot types available depends on the matplotlib backend in use on the system. Plot will not be displayed.
            :type filename: str
            :param fontsize: Size of font 
            :type fontsize: fl64
            :param xticks: Number of ticks along x axes
            :type xticks: int
        """        
        if mins is None and self._mins is not None: mins = self._mins
        if maxs is None and self._maxs is not None: maxs = self._maxs
        hd = hist(self.recarray, ncols=ncols, alpha=alpha, figsize=figsize, title=title, tight=tight, mins=mins, maxs=maxs,frequency=frequency,bins=bins,ylim=ylim,printout=printout,labels=labels,filename=filename,fontsize=fontsize,xticks=xticks)
        return hd
    def corr(self, type='pearson', plot=False, printout=True, plotvals=True, figsize=None, title=None):
        """ Calculate correlation coefficients of dataset values

            :param type: Type of correlation coefficient (pearson by default, spearman also avaialable)
            :type type: str
            :param plot: If True, plot correlation matrix
            :type plot: bool
            :param plotvals: If True, print correlation coefficients on plot matrix
            :type plotvals: bool
            :param printout: If True, print correlation matrix with row and column headings
            :type printout: bool
            :param figsize: Width and height of figure in inches
            :type figsize: tuple(fl64,fl64)
            :param title: Title of plot
            :type title: str
            :returns: ndarray(fl64) -- Correlation coefficients
        """
        return corr(self.recarray, self.recarray, type=type, plot=plot, printout=printout, plotvals=plotvals, figsize=figsize, title=title)
    def panels(self, type='pearson', alpha=0.2, figsize=None, title=None, tight=False, symbol='.',fontsize=None,corrfontsize=None,ms=5,mins=None,maxs=None,frequency=False,bins=10,ylim=None,labels=[],filename=None,xticks=2,yticks=2):
        """ Plot histograms, scatterplots, and correlation coefficients in paired matrix

            :param type: Type of correlation coefficient (pearson by default, spearman also avaialable)
            :type type: str
            :param alpha: Histogram color shading
            :type alpha: float
            :param figsize: Width and height of figure in inches
            :type figsize: tuple(fl64,fl64)
            :param title: Title of plot
            :type title: str
            :param tight: Use matplotlib tight layout
            :type tight: bool
            :param symbol: matplotlib symbol for scatterplots
            :type symbol: str
            :param corrfontsize: Size of font for correlation coefficients
            :type corrfontsize: fl64
            :param fontsize: Size of font for axis labels
            :type fontsize: fl64
            :param ms: Scatterplot marker size
            :type ms: fl64
            :param frequency: If True, the first element of the return tuple will be the counts normalized by the length of data, i.e., n/len(x)
            :type frequency: bool
            :param bins: If an integer is given, bins + 1 bin edges are returned. Unequally spaced bins are supported if bins is a list of sequences for each histogram.
            :type bins: int or lst(lst(int))
            :param ylim: y-axis limits for histograms.
            :type ylim: tuple - 2 element tuples with y limits for histograms
            :param labels: Names to use instead of parameter names in plot
            :type labels: lst(str)
            :param filename: Name of file to save plot. File ending determines plot type (pdf, png, ps, eps, etc.). Plot types available depends on the matplotlib backend in use on the system. Plot will not be displayed.
            :type filename: str
            :param xticks: Number of ticks along x axes 
            :type filename: int
            :param yticks: Number of ticks along y axes 
            :type filename: int
        """
        if mins is None and self._mins is not None: mins = self._mins
        if maxs is None and self._maxs is not None: maxs = self._maxs
        panels( self.recarray, type=type, alpha=alpha, figsize=figsize, title=title, tight=tight, symbol=symbol,fontsize=fontsize,corrfontsize=corrfontsize,ms=ms,mins=mins,maxs=maxs,frequency=frequency,bins=bins,ylim=ylim,labels=labels,filename=filename,xticks=xticks,yticks=yticks)

def corr(rc1, rc2, type='pearson', plot=False, printout=True, plotvals=True, figsize=None, title=None):
    """ Calculate correlation coefficients of parameters and responses

        :param rc1: Data
        :type type: Numpy structured (record) array
        :param rc2: Data
        :type type: Numpy structured (record) array
        :param type: Type of correlation coefficient (pearson by default, spearman also avaialable)
        :type type: str
        :param plot: If True, plot correlation matrix
        :type plot: bool
        :param printout: If True, print correlation matrix with row and column headings
        :type printout: bool
        :param plotvals: If True, print correlation coefficients on plot matrix
        :type plotvals: bool
        :param figsize: Width and height of figure in inches
        :type figsize: tuple(fl64,fl64)
        :param title: Title of plot
        :type title: str
        :returns: ndarray(fl64) -- Correlation coefficients
    """
    if numpy.any(numpy.isnan(rc1.tolist())) or numpy.any(numpy.isnan(rc2.tolist())):
        print "Error: Nan values exist probably due to failed simulations. Use subset (e.g. subset([('obs','!=',numpy.nan)]) to remove"
        return
    corrlist = []
    if type is 'pearson':
        for snm in rc1.dtype.names:
            corrlist.append([stats.pearsonr(rc1[snm],rc2[rnm])[0] for rnm in rc2.dtype.names])
    elif type is 'spearman':
        for snm in rc1.dtype.names:
            corrlist.append([stats.spearmanr(rc1[snm],rc2[rnm])[0] for rnm in rc2.dtype.names])
    else:
        print "Error: current types include 'pearson' and 'spearman'"
        return
    corrcoef = numpy.array(corrlist)
    # Print 
    if printout:
        dum = ' '
        print string.rjust(dum, 8),
        for nm in rc2.dtype.names:
            print string.rjust(nm, 8),
        print ''
        for i in range(corrcoef.shape[0]):
            print string.ljust(rc1.dtype.names[i], 8),
            for c in corrcoef[i]:
                print string.rjust('{:.2f}'.format(c), 8),
            print ''
    if plot and plotflag:
        # Plot
        plt.figure(figsize=figsize)
        plt.pcolor(numpy.flipud(corrcoef), vmin=-1, vmax=1)
        if plotvals:
            for i,ri in zip(range(corrcoef.shape[0]),reversed(range(corrcoef.shape[0]))):
                for j in range(corrcoef.shape[1]):
                    plt.text(j+0.4,i+0.4,'{:.2f}'.format(corrcoef[ri,j]),bbox=dict(facecolor='white'))
        plt.colorbar()
        if title:
            plt.title(title)
        plt.yticks(numpy.arange(0.5,len(rc1.dtype.names)+0.5),[nm for nm in reversed(rc1.dtype.names)])
        plt.xticks(numpy.arange(0.5,len(rc2.dtype.names)+0.5),rc2.dtype.names)
        plt.show()
    return corrcoef

def panels(rc, type='pearson', alpha=0.2, figsize=None, title=None, tight=False, symbol='.',fontsize=None,corrfontsize=None,ms=None,mins=None,maxs=None,frequency=False,bins=10,ylim=None,labels=[],filename=None,xticks=2,yticks=2):
    if plotflag:
        # Set font for scatterplot labels
        if not fontsize is None:
            font = {'size': fontsize}
            mplrc('font', **font)
        smp_mins = numpy.min(rc.tolist(),axis=0)
        smp_maxs = numpy.max(rc.tolist(),axis=0)
        if mins is None: mins = smp_mins
        else:
            mins = [ smp_mins[i] if mins[i] is None else mins[i] for i in range(len(mins)) ]
        if maxs is None: maxs = smp_maxs
        else:
            maxs = [ smp_maxs[i] if maxs[i] is None else maxs[i] for i in range(len(maxs)) ]
        if numpy.any(numpy.isnan(rc.tolist())):
            print "Error: Nan values exist probably due to failed simulations. Use subset (e.g. subset([('obs','!=',numpy.nan)]) to remove"
            return
        siz = len(rc.dtype)
        fig,ax = plt.subplots(siz,siz,figsize=figsize)
        ind = 1
        # Add axis labels to first column and last row
        if len(labels) == 0:
            labels = rc.dtype.names
        elif not len(labels) == len(rc.dtype.names):
            print "Error: number of labels does not match number of parameters"
            return
        for i,nm in enumerate(labels): 
            ax[i,0].set_ylabel(nm)
            ax[siz-1,i].set_xlabel(nm)        # Plot histograms in diagonal plots
        ns = []
        for i,nm in enumerate(rc.dtype.names): 
            if frequency:
                n,b,patches = ax[i,i].hist(rc[nm], alpha=alpha, range=(mins[i],maxs[i]), bins=bins, weights=numpy.ones(len(rc[nm])) / len(rc[nm]))
            else:
                n,b,patches = ax[i,i].hist(rc[nm], alpha=alpha, range=(mins[i],maxs[i]), bins=bins)
            ax[i,i].set_xlim([mins[i],maxs[i]])
            ns.append(n)
        # Set ylims of histograms
        if ylim is None:
            ymax = max([max(n) for n in ns])
            for i in range(len(rc.dtype)):
                ax[i,i].set_ylim([0,ymax])
        else:
            for i in range(len(rc.dtype)):
                ax[i,i].set_ylim(ylim)

        # Scatterplots in lower triangular matrix
        #if corrfontsize is None: corrfontsize = 2*siz
        for i,nm1 in enumerate(rc.dtype.names): 
            for j,nm2 in enumerate(rc.dtype.names): 
                if j<i:
                    ax[i,j].plot(rc[nm2],rc[nm1], symbol, ms=ms)
                    ax[i,j].axis([mins[j],maxs[j],mins[i],maxs[i]])
        # Print correlation coefficient in upper triangular matrix 
        corrcoef = corr(rc,rc,plot=False,printout=False)
        for i,nm1 in enumerate(rc.dtype.names): 
            for j,nm2 in enumerate(rc.dtype.names): 
                if j<i:
                    #ax[j,i].axis('off')
                    ax[j,i].text(0.5,0.5,str(numpy.round(corrcoef[j,i],2)),ha='center',va='center',size=corrfontsize,weight='bold')

        for i,nm1 in enumerate(rc.dtype.names): 
            for j,nm2 in enumerate(rc.dtype.names): 
                if j > 0:
                    ax[i,j].get_yaxis().set_visible(False)
                else:
                    ax[i,j].yaxis.set_major_locator(MaxNLocator(yticks))
                #    tk = ax[i,j].get_yticks()
                #    tk = [0.2*(tk[0]+tk[-1]),0.8*(tk[0]+tk[-1])]
                #    ax[i,j].set_yticks(tk)
                if i < len(rc.dtype)-1:
                    ax[i,j].get_xaxis().set_visible(False)
                else:
                    ax[i,j].xaxis.set_major_locator(MaxNLocator(xticks))
                #    tk = ax[i,j].get_xticks()
                #    tk = [0.2*(tk[0]+tk[-1]),0.8*(tk[0]+tk[-1])]
                #    ax[i,j].set_xticks(tk)

        if tight: 
            plt.tight_layout()
            if title:
                plt.subplots_adjust(top=0.925) 
        if title: plt.suptitle(title)
        if filename is None:
            plt.show()
        else:
            fmt = filename.split('.')[-1]
            plt.savefig(filename,format=fmt)
    else:
        print "Matplotlib must be installed to plot histograms"
        return
def hist(rc,ncols=4,figsize=None,alpha=0.2,title=None,tight=False,mins=None,maxs=None,frequency=False,bins=10,ylim=None,printout=True,labels=[],filename=None,fontsize=None,xticks=3):
    """ Plot histograms of dataset

        :param ncols: Number of columns in plot matrix
        :type ncols: int
        :param figsize: Width and height of figure in inches
        :type figsize: tuple(fl64,fl64)
        :param alpha: Histogram color shading
        :type alpha: float
        :param title: Title of plot
        :type title: str
        :param tight: Use matplotlib tight layout
        :type tight: bool
        :param mins: Minimum values of recarray fields
        :type mins: lst(fl64)
        :param maxs: Maximum values of recarray fields
        :type maxs: lst(fl64)
        :returns: dict(lst(int),lst(fl64)) - dictionary of histogram data (counts,bins) keyed by name
        :param frequency: If True, the first element of the return tuple will be the counts normalized by the length of data, i.e., n/len(x)
        :type frequency: bool
        :param bins: If an integer is given, bins + 1 bin edges are returned. Unequally spaced bins are supported if bins is a list of sequences for each histogram.
        :type bins: int or lst(lst(int))
        :param ylim: y-axis limits for histograms.
        :type ylim: tuples - 2 element tuple with y limits for histograms
        :param labels: Names to use instead of parameter names in plot
        :type labels: lst(str)
        :param filename: Name of file to save plot. File ending determines plot type (pdf, png, ps, eps, etc.). Plot types available depends on the matplotlib backend in use on the system. Plot will not be displayed.
        :type filename: str
        :param fontsize: Size of font 
        :type fontsize: fl64
        :param xticks: Number of ticks on xaxes
        :type xticks: int

    """        
    if plotflag:
        # Set font for scatterplot labels
        if not fontsize is None:
            font = {'size': fontsize}
            mplrc('font', **font)
        # Add axis labels to first column and last row
        if len(labels) == 0:
            labels = rc.dtype.names
        elif not len(labels) == len(rc.dtype.names):
            print "Error: number of labels does not match number of parameters"
            return
        smp_mins = numpy.min(rc.tolist(),axis=0)
        smp_maxs = numpy.max(rc.tolist(),axis=0)
        if mins is None: mins = smp_mins
        else:
            mins = [ smp_mins[i] if mins[i] is None else mins[i] for i in range(len(mins)) ]
        if maxs is None: maxs = smp_maxs
        else:
            maxs = [ smp_maxs[i] if maxs[i] is None else maxs[i] for i in range(len(maxs)) ]
        if numpy.any(numpy.isnan(rc.tolist())):
            print "Error: Nan values exist probably due to failed simulations. Use subset (e.g. subset([('obs','!=',numpy.nan)]) to remove"
            return
        siz = len(rc.dtype)
        if siz <= ncols:
            ncols = siz
            nrows = 1
        elif siz > ncols:
            nrows = int(numpy.ceil(float(siz)/ncols))
        else:
            nrows = 1
        if figsize is None:
            figsize = (ncols*3,nrows*3)
        fig = plt.figure(figsize=figsize)
        if mins is None: mins = numpy.min(rc.tolist(),axis=0)
        if maxs is None: maxs = numpy.max(rc.tolist(),axis=0)
        hist_dict = OrderedDict()
        ns = []
        ax = []
        for ind,nm,mi,ma,lb in zip(range(len(rc.dtype)),rc.dtype.names,mins,maxs,labels): 
            ax.append(plt.subplot(nrows,ncols,ind+1))
            if ind==0 or (ind)%ncols==0:
				if frequency: plt.ylabel('Frequency')
				else: plt.ylabel('Count')
            else: ax[-1].get_yaxis().set_visible(False)
            if frequency:
                n,b,patches = ax[-1].hist(rc[nm], range=[mi,ma], alpha=alpha, bins=bins, weights=numpy.ones(len(rc[nm])) / len(rc[nm]))
                hist_dict[nm] = (n,b,patches)
            else:
                n,b,patches = ax[-1].hist(rc[nm], range=[mi,ma], alpha=alpha, bins=bins)
                hist_dict[nm] = (n,b,patches)
            ax[-1].set_xlim([mi,ma])
            ns.append(n)
            plt.xlabel(lb)
            plt.locator_params(nbins=4)
            ax[-1].xaxis.set_major_locator(MaxNLocator(xticks))
        # Set ylims of histograms
        if ylim is None:
            ymax = max([max(n) for n in ns])
            for i in range(len(labels)):
                ax[i].set_ylim([0,ymax])
        else:
            for i in range(len(labels)):
                ax[i].set_ylim(ylim)
        if tight: 
            plt.tight_layout()
            if title:
                plt.subplots_adjust(top=0.925) 
        if title: plt.suptitle(title)
        if filename is None:
            plt.show()
        else:
            fmt = filename.split('.')[-1]
            plt.savefig(filename,format=fmt)
        if printout:
            for nm in hist_dict.keys():
                print '\n'
                print nm+':'
                if frequency: 
                    print ' Freq:',
                    flag=True
                    for n in hist_dict[nm][0]:
                        if flag: 
                            print '{:12.2f}'.format(n),
                            flag=False
                        else: print '{:8.2f}'.format(n),
                        #print '{:2f}'.format(n),
                else: 
                    print 'Count:',
                    flag=True
                    for n in hist_dict[nm][0]:
                        if flag:
                            print '{:12.0f}'.format(n),
                            flag=False
                        else:
                            print '{:8.0f}'.format(n),
                print '\n',
                print ' Bins:',
                flag=True
                for b in hist_dict[nm][1]:
                    if flag:
                        print '{:8.2g}'.format(b),
                        flag=False
                    else:
                        print '{:8.2g}'.format(b),
            print '\n'
        return hist_dict
    else:
        print "Matplotlib must be installed to plot histograms"
        return

