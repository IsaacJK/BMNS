# General libraries
import os, sys
import subprocess
import datetime
import pandas as pd
### Local BMNS Libraries ###
import src.FitData as fd
import src.SimR1p as sim
import src.SimFits as simf
import src.Errors as bme
import src.AMPGO as ampgo  # Global fitting
import src.MathFuncs as mf
import src.Stats as sf
import src.PlotMisc as pm
### Direct numpy imports ###
from numpy import absolute, array, asarray
from numpy import diag
from numpy import float64
from numpy import isinf, isnan
from numpy import linspace
from numpy import nan_to_num
from numpy import reshape
from numpy import sqrt
from numpy import zeros
### Numpy sub imports ###
from numpy.random import normal, seed
### Scipy/Other General Fitting Algs ###
from scipy.optimize import least_squares
# from leastsqbound import leastsqbound    # Local LS fits with bounds
# Uncertainties calculations
from uncertainties import ufloat

from joblib import Parallel, delayed
# import multiprocessing
from multiprocessing import Manager, Process, Pipe, Pool, cpu_count

#########################################################################
# Create a folder if it does not already exist #
#########################################################################
def makeFolder(pathToFolder):
    """
    Makes a folder from given path if
    it does not exist already.
    """
    if not os.path.exists(pathToFolder):
        os.makedirs(pathToFolder)

def Main():
    """
    #########################################################################
    # Bloch-McConnell 2-/3-state R1rho Fitting
    #########################################################################
    #  arg1 '-fit'
    #  arg2 Parameter Text File
    #       - See Example\ParExample.txt
    #  arg3 Parent directory of R1rho.csv data files
    #        corresponding to names in pars file.
    #       - Each csv is ordered:
    #          Col 1: Offset (corrected, Hz)
    #          Col 2: SLP (Hz)
    #          Col 3: R1rho (s-1)
    #          Col 4: R1rho err (s-1)[optional]
    #      If first row is text, will delete first row
    #       and first column, and shift col 2-5 to
    #       col 1-4, as above.
    #  arg4 Output directory for fit data [Optional]
    #         If not given, will generate folder in
    #         parent data directory.
    #-----------------------------------------------------------------------#
    """
    if "fit" in sys.argv[1].lower():
        ## Check if user wants to do a MC error estimation
        # number of MC iterations for error estimation
        if sys.argv[1].lower() == "-fitmc":
            # Try to assign MC it number to last arg
            try:
                if argc >= 6:
                    # Cast string arg for MC it num to int
                    fitMC = int(sys.argv[5])
                else:
                    fitMC = 100
            except ValueError:
                fitMC = 100
            mcerr = True # Flag for MC error estimation

        else:
            fitMC = 1
            mcerr = False # No MC error

        ## Check for Errors in Passed Arguments ##
        #  This function will terminate program if
        #   not all needed arguments or files are present
        bme.CheckArgs(curDir, argc, sys.argv)

        # Bool to determine if program succeeded in setup
        errBool = False
        # String for error messages.
        #  if runBool is ultimately False, these error messages will show up.
        retMsg = ""

        ## Define input/output Paths ##
        parPath = os.path.join(curDir, sys.argv[2])  # Path to input parameters
        dataPath = os.path.join(curDir, sys.argv[3]) # Path to parent dir of data
        if argc >= 5:                                # Handle output path (if exists)
            outPath = os.path.join(curDir, sys.argv[4])
            makeFolder(outPath)
        else: # If no output path given, create one in the data folder given above.
            outPath = os.path.join(curDir, dataPath, "Output/")
            makeFolder(outPath)
        # Make copies of input data and parameters
        copyPath = os.path.join(outPath, "Copies/")
        makeFolder(copyPath)
        subprocess.call(["cp", parPath, os.path.join(copyPath, "copy-input.txt")])

        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Parse given parameter input text file
        # Generate class objects for each corresponding given set of data
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ## Handle input parameter file ##
        # Generate a Data Parsing Class Object to handle input data
        pInp = fd.Parse()
        # Parse given input file to semi-raw format
        #  semi-raw can be handled by Parameters class
        pInp.ParseInp(parPath)
        # Check that given input parameter file is valid
        #  if not valid, set bool to false and return message
        errBool, tMsg = pInp.CheckPars(dataPath)
        # Perform Error checks on data parsing
        #  If fails, exit program
        retMsg += tMsg
        bme.HandleErrors(errBool, retMsg)

        ## Make Global class object to handle sub Fit class objects ##
        gl = fd.Global()

        # Generate fit objects and give them to Global class object
        #  Use index to assign FitNum to each Fit object
        for idx,inp in enumerate(pInp.ParInp):
            gl.gObs.append(fd.Fits(idx))

        ## Grab fit types
        gl.GrabFitType(pInp.FitType)
        if "int" in gl.FitType:
            dataType = "Ints"
        else:
            dataType = "R1p"
        ## Loop over fit objects in global class object
        #  Read in and convert parameter and data files
        for idx, i in enumerate(gl.gObs):
            # Convert semi-raw parameter data to Parameter self.Pars dictionary
            #  Also passes Variable names so that they can be seen to exist
            i.ConvertPars(pInp.ParInp[i.FitNum])
            # Parse and check raw R1rho data given the name in self.Pars
            #  of the corresponding Fit object
            #   Check to see if fit type specifies fitting for intensities with
            #   the 'int' keyword
            if "int" in gl.FitType:
                errBool, tMsg = pInp.ParseData(dataPath, i.name, dataType)
                retMsg += tMsg
            else:
                errBool, tMsg = pInp.ParseData(dataPath, i.name, dataType)
                retMsg += tMsg
            # print(i.name, i.Pars['pB_%s'%idx], i.Pars['pC_%s'%idx])

            # Copy original data
            subprocess.call(["cp", os.path.join(dataPath, i.name + ".csv"),
                             os.path.join(copyPath, "copy-" + i.name + ".csv")])
            # Check for any errors in parsing data
            bme.HandleErrors(errBool, retMsg)
            # Convert semi-raw data to Data class objects
            if "int" in gl.FitType:
                i.ConvertData(pInp.DataInp[i.FitNum], DataType = dataType)
            else:
                i.ConvertData(pInp.DataInp[i.FitNum], DataType = dataType)
            # Randomly remove data if flagged
            if i.deldata != 0.0:
                i.rnd_rem_data(i.deldata)

        ## Generate global P0, bounds, shared and fix value arrays, dicts and sets
        gl.MapGlobalP0()

        ## Calculate total degrees of freedom in data
        gl.CalcDOF(DataType = dataType)

        ## Make local, global and polished folders in outpath
        outLocal = os.path.join(outPath, "Local")
        outGlobal = os.path.join(outPath, "Global")
        outPolish = os.path.join(outPath, "Polish")
        # Make statistics output folder paths
        pstatsP = os.path.join(outPolish, "Matrices")
        lstatsP = os.path.join(outLocal, "Matrices")
        # Make output folders depending on fit type
        if gl.FitType == "global":
            makeFolder(outGlobal)
            makeFolder(outPolish)
            ## Make matrices folder path
            makeFolder(pstatsP) # Polished stats

        else:
            makeFolder(outLocal)
            makeFolder(lstatsP) # Local stats

        ## Create 'GraphOut' class object to handle graphing data
        #  this class object will handle graphing the fitted data
        grph = fd.GraphFit()

        # Last chance to catch errors
        if errBool == False:
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Fit Bloch-McConnell (2-/3-state) to experimental or simulated data
        #  Option to fit using R1rho error
        #   inData =
        #   P0 = Vector of initial guess for parameters for fit
        #        contents vary depending on parameters being fit
        #   time = vector of time increments (sec) from Tmin-Tmax
        #   lf = Larmor freq (MHz, to calc dw from ppm)
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            #---------------------------#---------------------------#
            # Chi-square local function used for fitting algorithms
            #  Returns chi-squares
            #   with error: chi-sq = ((R1p_sim - R1p)/(R1p_err))^2
            #   without error: chi-sq = (R1p_sim - R1p)^2 / R1p
            #---------------------------#---------------------------#
            def chi2(Params, DataType="R1p"):
                # Expected R1rho based on simulations
                chisq = 0.

                # Loop over all Fit objects in Global class object
                for ob in gl.gObs:
                    if DataType == "R1p":
                        # Unpack data
                        Offs, Spinlock = ob.R1pD[:,0], ob.R1pD[:,1]
                        R1p, R1p_e = ob.R1pD[:,2], ob.R1pD[:,3]
                        # Unpack parameters
                        lf = ob.lf
                        # Parse 'Params' down to only the local values
                        #  and handle shared and fix parameters.
                        tPars = gl.UnpackgP0(Params, ob)
                        # If error in value, chisq = (o-e/err)^2
                        if len(R1p_e) > 1:
                            chisq += sum([((sim.BMFitFunc(tPars,SL,-1.*OF,lf,ob.time,ob.AlignMag,0,kR1p)-kR1p)/err)**2.
                                           for (SL,OF,kR1p,err) in zip(Spinlock,Offs,R1p,R1p_e)])
                        # If no error in value, chisq = (o-e)^2/e
                        else:
                            chisq += sum([((sim.BMFitFunc(tPars,SL,-1.*OF,lf,ob.time,ob.AlignMag,0,kR1p)-kR1p)**2./kR1p)
                                          for (SL,OF,kR1p,err) in zip(Spinlock,Offs,R1p,R1p_e)])

                    # --- Get Intensity Residials --- #
                    elif DataType == "Ints":
                        # Unpack parameters
                        lf = ob.lf
                        # Parse 'Params' down to only the local values
                        #  and handle shared and fix parameters.
                        tPars = gl.UnpackgP0(Params, ob)
                        # Loop over index values in data
                        for d in ob.R1pD:
                            # Unpack data
                            Offs, SLPs = d[:,1], d[:,2]
                            Dlys, Ints, Ints_e = d[:,3], d[:,4], d[:,5]
                            # Simulated decay vector
                            pv = sim.BMFitFunc_ints(tPars, SLPs[0], -Offs[0],
                                                    lf, Dlys, ob.AlignMag)

                            # Calculate residual of this vector and the intensities
                            chisq += (((pv - Ints) / Ints_e)**2.).sum()

                ### Check for 'NaN' or 'inf' chi-square ###
                #  These are sometimes genereated when magnetization
                #   no longer decays as a simple monoexponential, and
                #   thus the log solve can be applied on a value <= 0
                #   which can return nan. Other exceptions that give
                #   inf can be related to the fitting algorthing
                # If true, returns a large number to disfavor this area.
                if isnan(chisq) == True or isinf(chisq) == True:
                    chisq = 1e4 # Return bad value
                return chisq

            #---------------------------#---------------------------#
            # Residual function used for fitting algorithms
            # R1p_MC (True/False) defines MC error  number
            # DataType specifies R1p or intensities to fit
            #  Returns matrix of residuals of: (f(x) - known) / error
            #                              or:  f(x) - known
            #---------------------------#---------------------------#
            def residual(Params, R1p_MC=None, DataType="R1p"):
                # Expected R1rho based on simulations
                resid = []
                # Loop over all Fit objects in Global class object
                for ob in gl.gObs:

                    # --- Get R1Rho Residials --- #
                    if DataType == "R1p":
                        # Unpack data
                        Offs, Spinlock = ob.R1pD[:,0], ob.R1pD[:,1]
                        R1p, R1p_e = ob.R1pD[:,2], ob.R1pD[:,3]

                        # Take in error corrupted R1p values
                        if R1p_MC is not None:
                            R1p = ob.R1p_MC
                        # Unpack parameters
                        lf = ob.lf
                        # Parse 'Params' down to only the local values
                        #  and handle shared and fix parameters.
                        tPars = gl.UnpackgP0(Params, ob)
                        # Calculate residuals using BM numerical solution
                        #  if equation is specified in ob.fitEqn
                        if gl.gFitEqn == "bm":
                            # If error in value, residual matrix = (f(x) - obs) / err
                            if len(R1p_e) > 1 and R1p_MC is None:
                                resid += [(absolute(sim.BMFitFunc(tPars,SL,-1.*OF,lf,ob.time,ob.AlignMag,0,kR1p)-kR1p)/err)
                                               for (SL,OF,kR1p,err) in zip(Spinlock,Offs,R1p,R1p_e)]

                            # If no error in value, residual matrix = f(x) - obs
                            else:
                                resid += [(sim.BMFitFunc(tPars,SL,-1.*OF,lf,ob.time,ob.AlignMag,0,kR1p)-kR1p)
                                               for (SL,OF,kR1p) in zip(Spinlock,Offs,R1p)]
                        # Calculate residuals using Laguerre approximations
                        elif gl.gFitEqn == "lag":
                            # If error in value, residual matrix = (f(x) - obs) / err
                            if len(R1p_e) > 1 and R1p_MC is None:
                                resid += [((sim.LagFitFunc(tPars,SL,-1.*OF,lf,ob.time,ob.AlignMag,0,kR1p)-kR1p)/err)
                                               for (SL,OF,kR1p,err) in zip(Spinlock,Offs,R1p,R1p_e)]

                            # If no error in value, residual matrix = f(x) - obs
                            else:
                                resid += [(sim.LagFitFunc(tPars,SL,-1.*OF,lf,ob.time,ob.AlignMag,0,kR1p)-kR1p)
                                              for (SL,OF,kR1p) in zip(Spinlock,Offs,R1p)]
                    # --- Get Intensity Residials --- #
                    elif DataType == "Ints":
                        # Unpack parameters
                        lf = ob.lf
                        # Parse 'Params' down to only the local values
                        #  and handle shared and fix parameters.
                        tPars = gl.UnpackgP0(Params, ob)

                        # Take in error corrupted R1p values
                        if R1p_MC is not None:
                            # Loop over index values in data
                            for d in ob.R1pD_MC:
                                # Unpack data
                                Offs, SLPs = d[:,1], d[:,2]
                                Dlys, Ints, Ints_e = d[:,3], d[:,4], d[:,5]

                                # Simulated decay vector
                                pv = sim.BMFitFunc_ints(tPars, SLPs[0], -Offs[0],
                                                        lf, Dlys, ob.AlignMag)
                                # Calculate residual of this vector and the intensities
                                resid.append(absolute((pv - Ints) / Ints_e))
                        # No error corrupted intensities
                        else:
                            # Loop over index values in data
                            for d in ob.R1pD:
                                # Unpack data
                                Offs, SLPs = d[:,1], d[:,2]
                                Dlys, Ints, Ints_e = d[:,3], d[:,4], d[:,5]

                                # Simulated decay vector
                                pv = sim.BMFitFunc_ints(tPars, SLPs[0], -Offs[0],
                                                        lf, Dlys, ob.AlignMag)
                                # Calculate residual of this vector and the intensities
                                resid.append(absolute((pv - Ints) / Ints_e))

                resid = asarray(resid)
                if DataType == "Ints":
                    # If fit for ints, reshape residual as flat array
                    resid = reshape(resid, resid.shape[0] * resid.shape[1])

                ### Check for 'NaN' or 'inf' chi-square ###
                #  These are sometimes genereated when magnetization
                #   no longer decays as a simple monoexponential, and
                #   thus the log solve can be applied on a value <= 0
                #   which can return nan. Other exceptions that give
                #   inf can be related to the fitting algorthing
                # If true, replace nan/inf elements with zero (nan)
                #  or large positive (inf) or large negative (-inf) values
                if isnan(resid).any() == True or isinf(resid).any() == True:
                    resid = nan_to_num(resid) # Replace nan or inf values
                return resid

            #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Primary fitting loop.
            #  Loops over gl.FitLoops N times (i.e. finds N times fit minima)
            #  Embedded if statement around gl.FitType dictates if the fit
            #   is carried out globally (with polish) or locally.
            #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            for lp in range(gl.FitLoops):
                if gl.FitType == "global":
                    print("~~~~~~~~~~~~~~~~~ GLOBAL FIT START (%s) ~~~~~~~~~~~~~~~~~" % str(lp+1))
                    print("  (Adaptive Memory Programming for Global Optimums)  ")
                    if mcerr == True:
                        print('''   * Monte-Carlo error flagged but will not
                          be estimated with global fits *''')
                    # Randomize initial guess, if flagged
                    if gl.rndStart == True:
                        tP0 = gl.RandomgP0()
                    else:
                        tP0 = gl.gP0
                    # Convert bounds array to tuple for use in AMPGO algorithm
                    bnds = tuple((x,y) for x,y in zip(gl.gBnds[0], gl.gBnds[1]))
                    fitted = ampgo.AMPGO(chi2, tP0, local='L-BFGS-B',
                                         bounds=bnds, maxiter=5, tabulistsize=8,
                                         totaliter=10, disp=0, maxfunevals=2000)

                    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    ### Update Fit (global) Class Objects Here ###
                    # 1. Unpack global fitted parameters
                    # 2. Write out fits and reduced chi^2 (chi-sq/dof)
                    # 3. Write out graphs of fitted R1rho and R2+Rex and the residuals
                    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    for ob in gl.gObs:
                        # Reduced chi-square = chi-square / (N (data points) - M (free parameters))
                        redChiSq = fitted[1] / gl.dof
                        # Unpack global fit param array to local values for Fit object
                        gl.UnPackFits(lp+1, gl.UnpackgP0(fitted[0], ob), redChiSq, fitted[2], "global", ob)

                        # Write out / append latest fit data
                        gl.WriteFits(outPath, ob, lp+1, "global")

                        # Graph fitted data with trend-lines, and also export R1rho/R2eff values
                        grph.WriteGraph(ob, outGlobal, lp+1, ob.time, "global")

                    print("     Polish Global Fit with Levenberg-Marquardt")

                    # !! For least_squares function/Lev-Mar !! #
                    fitted = least_squares(residual, fitted[0], bounds = gl.gBnds, max_nfev=10000)

                    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    ### Update Fit (polish) Class Objects Here ###
                    # 1. Unpack local fitted parameters
                    # 2. Write out fits and reduced chi^2 (chi-sq/dof)
                    # 3. Write out graphs of fitted R1rho and R2+Rex and the residuals
                    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    for ob in gl.gObs:
                        # Reduced chi-square = chi-square / (N (data points) - M (free parameters))
                        chisq = chi2(fitted.x)
                        redChiSq = chisq / gl.dof

                        # Calculate fit error
                        #   Here: Standard error of the fit is used
                        fiterr,_,_,_ = sf.cStdErr(fitted.x, fitted.fun, fitted.jac, gl.dof)

                        # Unpack global fit param array to local values for Fit object
                        gl.UnPackFits(lp+1, gl.UnpackgP0(fitted.x, ob), redChiSq,
                                      fitted.nfev, "polish", ob, errPars=gl.UnpackErr(fiterr, ob))

                        # Write out / append latest fit data
                        gl.WriteFits(outPath, ob, lp+1, "polish")

                        # Graph fitted data with trend-lines, and also export R1rho/R2eff values
                        grph.WriteGraph(ob, outPolish, lp+1, ob.time, "polish")

                        # Calculate fit stats
                        sf.WriteStats(outPath, pstatsP, fitted, ob, gl.dof, gl.dataSize,
                                      gl.freePars, chisq, redChiSq, lp+1, "polish")
                # Local Fit
                elif gl.FitType == "local":
                    print("~~~~~~~~~~~~~~~~~ LOCAL FIT START (%s) ~~~~~~~~~~~~~~~~~" % str(lp+1))
                    print("                 (Levenberg-Marquardt)  ")

                    # Randomize initial guess, if flagged
                    if gl.rndStart == True:
                        tP0 = gl.RandomgP0()
                    else:
                        tP0 = gl.gP0
                    # Least_squares / Lev-Mar fit
                    fitted = least_squares(residual, tP0, bounds = gl.gBnds, max_nfev=10000,
                                           method='trf')

                    # This will estimate R1p parameter errors as standard dev
                    #  from MC normal error corruption and re-fit of R1p vals
                    if mcerr == True:
                        tpars = []
                        # Error corrupt R1p values normally around mu=R1p, sigma=R1p_err
                        for i in range(fitMC):
                            # Print out MC iteration number to terminal - flush
                            sys.stdout.write("\r    --- Monte-Carlo Error Estimation (%s of %s) ---" % (i+1, fitMC))
                            sys.stdout.flush()
                            # Iterate over sub ojects in fit
                            for ob in gl.gObs:
                                ob.R1p_MC = array([normal(y, ye) for y, ye in zip(ob.R1pD[:,2], ob.R1pD[:,3])])
                            # Fit noise-corrupted R1p data, append fits only to list
                            tpars.append(least_squares(residual, fitted.x, bounds = gl.gBnds, max_nfev=10000,
                                                                                args=([True])).x)
                        # Combine all fit parameters to one numpy array
                        MCpars = asarray(tpars).astype(float64)

                    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    ### Update Fit (local) Class Objects Here ###
                    # 1. Unpack local fitted parameters
                    # 2. Write out fits and reduced chi^2 (chi-sq/dof)
                    # 3. Write out graphs of fitted R1rho and R2+Rex and the residuals
                    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    for ob in gl.gObs:
                        # Reduced chi-square = chi-square / (N (data points) - M (free parameters))
                        chisq = chi2(fitted.x)
                        redChiSq = chisq / gl.dof

                        # Calculate fit error
                        if mcerr == False:
                            #   Here: Standard error of the fit is used
                            if ob.R1pD[:,3].sum() != 0.:
                                fiterr,_,_,_ = sf.cStdErr(fitted.x, fitted.fun,
                                                          fitted.jac, gl.dof)
                            else:
                                fiterr = zeros(fitted.x.shape)
                        # Handle MC error write out and plotting
                        else:
                            #   Here: Monte-Carlo parameter error estimation
                            fiterr = MCpars.std(axis=0)
                            # Get all indv red chi-sqs
                            RCS_list = array([chi2(x)/gl.dof for x in MCpars])
                            # Write out MC error corrupted fits to separate CSV
                            for idx,(f,r) in enumerate(zip(MCpars, RCS_list)):
                                # Unpack MC err corrupt fits to object mcfits
                                gl.UnPackFits(idx+1, gl.UnpackgP0(f, ob), r,
                                              fitted.nfev, "mcerr", ob, errPars=gl.UnpackErr(fiterr, ob))
                                # Write out / append MC error corrupted fit data
                                gl.WriteFits(outPath, ob, idx+1, "mcerr")

                        # Unpack global fit param array to local values for Fit object
                        gl.UnPackFits(lp+1, gl.UnpackgP0(fitted.x, ob), redChiSq,
                                      fitted.nfev, "local", ob, errPars=gl.UnpackErr(fiterr, ob))
                        # Write out / append latest fit data
                        gl.WriteFits(outPath, ob, lp+1, "local")

                        # Graph fitted data with trend-lines, and also export R1rho/R2eff values
                        grph.WriteGraph(ob, outLocal, lp+1, ob.time, FitType="local", FitEqn=gl.gFitEqn)

                        # Calculate fit stats
                        sf.WriteStats(outPath, lstatsP, fitted, ob, gl.dof, gl.dataSize,
                                      gl.freePars, chisq, redChiSq, lp+1, "local")
                # Fit intensity values directly using local optimization
                elif gl.FitType == "localint":
                    print("~~~~~~~~~~~~~~~~~ LOCAL INTENSITY FIT START (%s) ~~~~~~~~~~~~~~~~~" % str(lp+1))
                    print("                     (Levenberg-Marquardt)  ")

                    # Randomize initial guess, if flagged
                    if gl.rndStart == True:
                        tP0 = gl.RandomgP0()
                    else:
                        tP0 = gl.gP0
                    td = gl.gObs[0].R1pD

                    # Least_squares / Lev-Mar fit
                    fitted = least_squares(residual, tP0, bounds = gl.gBnds, max_nfev=10000,
                                           method='trf', kwargs={'DataType': 'Ints'})

                    # This will estimate R1p parameter errors as standard dev
                    #  from MC normal error corruption and re-fit of R1p vals
                    if mcerr == True:

                        tpars = []
                        # Error corrupt R1p values normally around mu=R1p, sigma=R1p_err
                        for i in range(fitMC):
                            # Print out MC iteration number to terminal - flush
                            sys.stdout.write("\r    --- Monte-Carlo Error Estimation (%s of %s) ---" % (i+1, fitMC))
                            sys.stdout.flush()

                            # Iterate over sub ojects in fit
                            for ob in gl.gObs:
                                # Copy real int data to MC array for error corruption
                                ob.R1pD_MC = ob.R1pD.copy()
                                for d, c in zip(ob.R1pD, ob.R1pD_MC):
                                    # Noise corrupt intensities by error
                                    c[:,4] = array([normal(y, ye) for y, ye in zip(d[:,4], d[:,5])])

                            # Fit noise-corrupted R1p data, append fits only to list
                            tpars.append(least_squares(residual, fitted.x, bounds = gl.gBnds, max_nfev=10000,
                                                       kwargs={'R1p_MC': True, 'DataType': 'Ints'}).x)

                        # Combine all fit parameters to one numpy array
                        MCpars = asarray(tpars).astype(float64)

                    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    ### Update Fit (local) Class Objects Here ###
                    # 1. Unpack local fitted parameters
                    # 2. Write out fits and reduced chi^2 (chi-sq/dof)
                    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    for ob in gl.gObs:
                        # Reduced chi-square = chi-square / (N (data points) - M (free parameters))
                        chisq = chi2(fitted.x, DataType=dataType)
                        redChiSq = chisq / gl.dof

                        if mcerr == False:
                            # #   Here: Standard error of the fit is used
                            if ob.R1pD[:,0][:,5].sum() != 0.:
                                fiterr,_,_,_ = sf.cStdErr(fitted.x, fitted.fun,
                                                          fitted.jac, gl.dof)
                            else:
                                fiterr = zeros(fitted.x.shape)

                        # Handle MC error write out and plotting
                        else:
                            #   Here: Monte-Carlo parameter error estimation
                            fiterr = MCpars.std(axis=0)
                            # Get all indv red chi-sqs
                            RCS_list = array([chi2(fitted.x, DataType=dataType)/gl.dof for x in MCpars])
                            # Write out MC error corrupted fits to separate CSV
                            for idx,(f,r) in enumerate(zip(MCpars, RCS_list)):
                                # Unpack MC err corrupt fits to object mcfits
                                gl.UnPackFits(idx+1, gl.UnpackgP0(f, ob), r,
                                              fitted.nfev, "mcerr", ob, errPars=gl.UnpackErr(fiterr, ob))
                                # Write out / append MC error corrupted fit data
                                gl.WriteFits(outPath, ob, idx+1, "mcerr")

                        # Unpack global fit param array to local values for Fit object
                        gl.UnPackFits(lp+1, gl.UnpackgP0(fitted.x, ob), redChiSq,
                                      fitted.nfev, "local", ob, errPars=gl.UnpackErr(fiterr, ob))
                        # Write out / append latest fit data
                        gl.WriteFits(outPath, ob, lp+1, "local")

                        # Graph fitted decays with B-M simulations
                        #  get array of full params
                        fPars = gl.UnpackgP0(fitted.x, ob)
                        grph.PlotDecays(ob, outLocal, fPars, lp+1, FitType="local")

                        # Calculate fit stats
                        sf.WriteStats(outPath, lstatsP, fitted, ob, gl.dof, gl.dataSize,
                                      gl.freePars, chisq, redChiSq, lp+1, "local")

                # Brute-force fit intensitites across parameter space
                elif gl.FitType == "bruteint" or gl.FitType == "bruteintp":
                    pass
                # Brute-force across parameter range
                elif gl.FitType == "brute" or gl.FitType == "brutep":
                    #########################################################################
                    # Monte-Carlo multiprocessing functions used to avoid
                    #  pickling error in multiprocessing.Process function
                    #  when function called within function
                    # Used from: http://stackoverflow.com/questions/3288595/
                    #            multiprocessing-using-pool-map-on-a-function-defined-in-a-class
                    #########################################################################

                    def fun(f,q_in,q_out):
                      while True:
                        i,x = q_in.get()
                        if i is None:
                            break
                        q_out.put((i,f(x)))

                    def parmap(f, X, nprocs = cpu_count()):
                        m = Manager()
                        q_in   = m.Queue(1)
                        q_out  = m.Queue()

                        proc = [Process(target=fun,args=(f,q_in,q_out)) for _ in range(nprocs)]
                        for p in proc:
                          p.daemon = True
                          p.start()

                        sent = [q_in.put((i,x)) for i,x in enumerate(X)]
                        [q_in.put((None,None)) for _ in range(nprocs)]
                        res = [q_out.get() for _ in range(len(sent))]
                        [p.join() for p in proc]

                        return [x for i,x in sorted(res)]

                    # Define the Monte-Carlo random corrupt look
                    def Brute_loop(idx):
                        gf = gl.brutegP0[idx]
                        print("    Iteration %s of %s" % (idx+1, len(gl.brutegP0)))
                        allfits = {}
                        # Don't let it fit, just 1 iteration
                        fitted = least_squares(residual, gf, bounds = gl.gBnds, max_nfev=1)
                        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                        ### Update Fit (local) Class Objects Here ###
                        # 1. Unpack local fitted parameters
                        # 2. Write out fits and reduced chi^2 (chi-sq/dof)
                        # 3. Write out graphs of fitted R1rho and R2+Rex and the residuals
                        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                        for ob in gl.gObs:
                            # Reduced chi-square = chi-square / (N (data points) - M (free parameters))
                            chisq = chi2(fitted.x)
                            redChiSq = chisq / gl.dof
                            # Store all the fits
                            allfits[redChiSq] = gf

                            # Calculate fit error
                            #   Here: Standard error of the fit is used
                            fiterr,_,_,_ = sf.cStdErr(fitted.x, fitted.fun, fitted.jac, gl.dof)

                            # Unpack global fit param array to local values for Fit object
                            gl.UnPackFits(idx+1, gl.UnpackgP0(fitted.x, ob), redChiSq,
                                          fitted.nfev, "local", ob, errPars=gl.UnpackErr(fiterr, ob))
                            # Write out / append latest fit data
                            gl.WriteFits(outPath, ob, idx+1, "local")

                            # If flagged in input file, generate graphs for all curves
                            if gl.FitType == "brutep":
                                # Graph fitted data with trend-lines, and also export R1rho/R2eff values
                                grph.WriteGraph(ob, outLocal, idx+1, ob.time, FitType="local", FitEqn=gl.gFitEqn)

                            # Calculate fit stats
                            sf.WriteStats(outPath, lstatsP, fitted, ob, gl.dof, gl.dataSize,
                                          gl.freePars, chisq, redChiSq, idx+1, "local", matrices=False)
                        return allfits
                    print("--- BRUTE FORCE PARAMETER SPACE ---")
                    # Keep track of reduced chi-squares mapped to P0 array
                    # Split brute fitting over N-cores
                    allfits = parmap(Brute_loop, list(range(len(gl.brutegP0))))
                    allfits = dict(allfits[0])

                    # Start the last fit, from the best fit
                    print("\n    Lowest red. chi-square found. Minimizing within bounds.    ")
                    lastval = len(gl.brutegP0) + 1
                    tP0 = allfits[min(allfits.keys())]
                    # Least_squares / Lev-Mar fit
                    fitted = least_squares(residual, tP0, bounds = gl.gBnds, max_nfev=10000)
                    # fitted = least_squares(residual, tP0, max_nfev=10000)
                    for ob in gl.gObs:
                        # Reduced chi-square = chi-square / (N (data points) - M (free parameters))
                        chisq = chi2(fitted.x)
                        redChiSq = chisq / gl.dof

                        # Calculate fit error
                        #   Here: Standard error of the fit is used
                        fiterr,_,_,_ = sf.cStdErr(fitted.x, fitted.fun, fitted.jac, gl.dof)

                        # Unpack global fit param array to local values for Fit object
                        gl.UnPackFits(lastval, gl.UnpackgP0(fitted.x, ob), redChiSq,
                                      fitted.nfev, "local", ob, errPars=gl.UnpackErr(fiterr, ob))
                        # Write out / append latest fit data
                        gl.WriteFits(outPath, ob, lastval, "local")

                        # Graph fitted data with trend-lines, and also export R1rho/R2eff values
                        grph.WriteGraph(ob, outLocal, lastval, ob.time, FitType="local", FitEqn=gl.gFitEqn)

                        # Calculate fit stats
                        sf.WriteStats(outPath, lstatsP, fitted, ob, gl.dof, gl.dataSize,
                                      gl.freePars, chisq, redChiSq, lastval, "local")

                else:
                    print("Fit Type not declared properly (global or local)")

        else:
            print("----- Cannot Run Fit Because of Errors -----")
            print(retMessage)

    #########################################################################
    # Bloch-McConnell 2-/3-state R1rho Simulation
    #########################################################################
    #  arg1 '-sim'
    #  arg2 Parameter Text File
    #  arg3 (Optional) Specific output folder, will be made if does not exist
    #-----------------------------------------------------------------------#
    elif sys.argv[1].lower() == "-sim":
        # Create parent output directory
        if len(sys.argv) >= 4:
            outPath = os.path.join(curDir, sys.argv[3])
            makeFolder(outPath)
        else:
            # Get timestamp for generating folder
            mydate = datetime.datetime.now()
            tst = mydate.strftime("Simulation_%m%d%y-%H%Mh%Ss")
            outPath = os.path.join(curDir, tst)
            makeFolder(outPath)
        # Make copies of input parameter file
        outCopy = os.path.join(outPath, "Copies")
        makeFolder(outCopy)
        # Create folder for all magnetization vectors
        outVec = os.path.join(outPath, "MagVecs")
        makeFolder(outVec)
        # Create simulation class object
        sfo = simf.SimFit()
        # Clean and handle input args
        sfo.PreSim(sys.argv, outCopy)
        # Simulate R1rho values
        sfo.simFit()
        # Plot R1rho values
        sfo.plotR1p(outPath)
        # Plot R2eff values
        sfo.plotR2eff(outPath)
        # Plot onres R1rho values
        sfo.plotOnRes(outPath)
        # Plot monoexponential decays
        sfo.plotDec(outPath)
        # Write-out simulated R1rho values
        sfo.writeR1p(outPath)
        # Write-out simulated vectors and eigenvalues
        sfo.writeSimPars(outPath)
        # Write-out sim parameters
        sfo.writeVecVal(outVec, outPath)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3D Magnetization Visualization
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #  arg1 '-3d'
    #  arg2 Magnetization vector CSV from simulation
    # Plots the 3D decay of coherence
    #---------------------------------------------------
    elif "3d" in sys.argv[1].lower():
        # Create simulation class object
        sfo = simf.SimFit()
        sfo.plot3DVec(sys.argv[2])
        #VecAnimate3D(M_4)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Tab to CSV splitter
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #  arg1 '-tab2csv'
    #  arg2 Tab delimited file
    # Will dump csv file of same name to same directory
    #---------------------------------------------------
    elif (argc == 3 and sys.argv[1].lower() == "-tab2csv"
          and os.path.isfile(os.path.join(curDir, sys.argv[2]))):
        tabPath = os.path.join(curDir, sys.argv[2])
        csvPath = os.path.join(curDir, sys.argv[2].replace(".tab",".csv"))
        with open(tabPath, "r") as file:
            tabData = [x.strip().split() for x in file]

        with open(csvPath, "wb") as file:
            for line in tabData:
                file.write(",".join(line) + "\n")

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Compare fitted models using statistics files
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #  arg1 '-compare'
    #  arg2 list of model csvs
    # This will compare the first row of each model csv
    #  to each other model to calculate best fit model
    #---------------------------------------------------
    elif sys.argv[1].lower() == "-compare":
        paths = []
        # Get all fit models
        for i in sys.argv[2:]:
            if os.path.isfile(os.path.join(curDir, i)):
                paths.append(os.path.join(curDir, i))
            else:
                print("Model ( %s ) does not exist." % i)
        # Make sure at least 2 models to compare
        if len(paths) >= 2:
            sf.CompareModels(paths)
        else:
            print("Not enough models to compare.")

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Calculate thermodynamic parameters from fit file
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #  arg1 '-thermo'
    #  arg2 BMNS fit .csv file
    # Will append thermo values to fit file
    #---------------------------------------------------
    elif argc == 4 and sys.argv[1].lower() == "-thermo" \
         and os.path.isfile(os.path.join(curDir, sys.argv[2])):
        # Path to BMNS fit csv file
        pPath = os.path.join(curDir, sys.argv[2])

        # Temperature (Kelvin), assume 0.2K error
        try:
            # Assume spectrometer variance of +/- 0.2K in parameter
            te = ufloat(sys.argv[3], 0.2)
            if te.n < 100.:
                print("Temperature seems to be in centigrade instead of Kelvin")
                print("  Converting from %sC to %sK" % (te.n, te.n + 273.15))
                te = ufloat(te.n + 273.15, 0.2)
        except ValueError:
            print("Invalid temperature given (%s)" % sys.argv[3])
            print("  Setting temperature to 298K")

        # Data to append thermo parameters to and write out
        outData = []
        outPath = pPath.replace(".csv", "") + "_thermo_%0.1f.csv" % te.n

        # Define parse class object
        pInp = fd.Parse()

        # Parse fit data
        fitd = pInp.ParseFitCSV(pPath)

        # Start loop over fit values
        for fit in fitd:
            # Check to make sure not the header
            if fit[0] != "Name":
                # Get populations
                pB = array([fit[5], fit[18]]).astype(float)
                pC = array([fit[6], fit[19]]).astype(float)
                # Get observed rate constants
                #  Make them as numpy array of [val, error]
                kexAB = array([fit[9], fit[22]]).astype(float)
                kexAC = array([fit[10], fit[23]]).astype(float)
                kexBC = array([fit[11], fit[24]]).astype(float)
                # Get rate constants and lifetimes of excited
                #  states and ground-state
                k12, k21, k13, k31, k23, k32, tau1, tau2, tau3 \
                  = mf.CalcRateTau(pB, pC, kexAB, kexAC, kexBC)
                # Get free energies and energetic barriers
                dG12, ddG12, ddG21, dG13, ddG13, ddG31, ddG23, ddG32 \
                  = mf.CalcG(te, k12, k21, k13, k31, k23, k32, pB, pC)
                # Append old data and new data to output data
                outData.append(",".join(fit) +
                  ",".join([
                  str(k12.n), str(k21.n), str(k13.n), str(k31.n), str(k23.n), str(k32.n),
                  str(tau1.n), str(tau2.n), str(tau3.n),
                  str(dG12.n), str(ddG12.n), str(ddG21.n),
                  str(dG13.n), str(ddG13.n), str(ddG31.n),
                  str(ddG23.n), str(ddG32.n),
                  str(k12.std_dev), str(k21.std_dev), str(k13.std_dev), str(k31.std_dev),
                  str(k23.std_dev), str(k32.std_dev),
                  str(tau1.std_dev), str(tau2.std_dev), str(tau3.std_dev),
                  str(dG12.std_dev), str(ddG12.std_dev), str(ddG21.std_dev),
                  str(dG13.std_dev), str(ddG13.std_dev), str(ddG31.std_dev),
                  str(ddG23.std_dev), str(ddG32.std_dev)]) + ",\n")
            # Handle header
            else:
                headerStr = ",".join(fit) + "k12,k21,k13,k31,k23,k32," \
                  + "tau1,tau2,tau3," \
                  + "dG12,ddG12,ddG21,dG13,ddG13,ddG31,ddG23,ddG32," \
                  + "k12_err,k21_err,k13_err,k31_err,k23_err,k32_err," \
                  + "tau1_err,tau2_err,tau3_err," \
                  + "dG12_err,ddG12_err,ddG21_err,dG13_err,ddG13_err,ddG31_err,ddG23_err,ddG32_err,\n"
                outData.append(headerStr)
        # Write out fit data
        with open(outPath, "w") as file:
            for line in outData:
                file.write(line)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Plot brute-force graphs
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #  arg1 '-plotbrute'
    #  arg2 Brute-force parameter plot
    #  arg3 Parameter name 1
    #  arg4 Parameter name 2
    #---------------------------------------------------
    elif sys.argv[1].lower() == "-plotbrute" or sys.argv[1].lower() == "-plotbrute0":
        pm.PlotBrute(sys.argv, curDir)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Update self
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #  arg1 '-update'
    #---------------------------------------------------
    elif sys.argv[1].lower() == "-update":
        pass

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Generate Example Simulation Input file
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #  arg1 '-gensim'
    #  arg2 output directory
    #---------------------------------------------------
    elif sys.argv[1].lower() == "-gensim":
        outstr = '''
##################################################################################
# Run the BMNS simulation routine:
# > python BMNS.py -sim [BM Simulation Input File] (Optional Output directory)
##################################################################################
# "Params" block is where simulation parameters are defined.
#   Parameters can be defined manually, or read-in from a BM-fit CSV file
# If you read in fit CSV you can then manually define some parameters,
#   this will overwrite the parameters read in from CSV.
#---------------------------------------------------------------------------------
# - 'Read' reads in a BM fit csv file from local directory
#     only uses kexAB, kexAC, kexBC for exchange rates, not indv rate constants
#   This can replace or complement the individually specified values
# - 'lf' is larmor frequency of spin (e.g. 150.8MHz for 13C, etc)
# - 'AlignMag' is auto/gs/avg for automatic, ground-state, or average alignment
# - 'pB/pC' are populations of state B/C
# - 'kexAB/AC/BC' are exchange rates between the 3 states A,B, and C
# - 'R1/R2' are the intrinsic relax rates of states A/B/C
# Any of the above parameters can be commented out provided they are read-in
#  from a CSV file instead.
##################################################################################
+
Params
#Read pars.csv
lf 150.784627
AlignMag Auto
pB 0.01
pC 0.0
dwB 3.0
dwC 0.0
kexAB 3000.0
kexAC 0.0
kexBC 0.0
R1 2.5
R2 16.0
R1b 2.5
R2b 16.0
R1c 2.5
R2c 16.0

##################################################################################
# "SLOFF" block defines spinlock powers and offsets to simulate with BM.
# Additionally, real data can be read in to be overlaid with simulated data.
# Additionally, simulated data can be error corrupted at the level of the
#     R1rho value to a certain percentage. Monte-Carlo iterations can be
#   defined for this error corruption.
#---------------------------------------------------------------------------------
# - 'Read' defines a .csv file that can be read in
#       that contains Offset(Hz), SLP(Hz) in columns
#       and these will be simulated. If commented out
#     then they will not be read in.
# - 'Data' defines a .csv file that contains real data.
#      Can directly read in data file generated by
#     the BM fitting routine.
#   Order is:
#    Col1: Corrected Offset(Hz)
#    Col2: SLP (Hz)
#    Col3: R1rho
#    Col4: R1rho error (must exist, even if all zeros)
#    Col5: R2eff
#    Col6: R2eff error (must exist, even if all zeros)
#   If not defined, then they will not be read in.
# - 'Error' noise corruption for simulated R1rho values.
#   e.g. 0.02 would error corrupt R1rho by 2%%
#   Generates error from MC error corruption, selecting
#   sigma from gaussian distribution around corrupted
#   R1rho value
# - 'MCNum' defines number of MC iterations for noise corruption.
# - 'on' Defines on-resonance R1rho values to be simulated
#  Add as many of these as you wish
#     Col1: 'on'
#   Col2: Lower SLP (Hz)
#   Col3: Upper SLP (Hz)
#   Col4: Number of onres SLPs to simulate between low/high
# - 'off' defines off-resonance R1rho values to be simulated
#   at a given SLP over a range of offsets.
#    Add as many 'off' rows as you need to generate more
#   more off-resonance points or spinlock powers
#     Col1: 'off'
#   Col2: SLP (Hz)
#   Col3: Lower Offset (Hz)
#   Col4: Upper Offset (Hz)
#   Col5: Number of offres SLPs to simulate between low/high
##################################################################################
+
SLOFF
#Read sloffs.csv
#Data data.csv
Error 0.0
MCNum 500
on 100 3500 50
off 100 -1000 1000 200
off 200 -1000 1000 200
off 400 -1000 1000 200
#off 800 -1000 1000 200
#off 1600 -1000 1000 200
#off 3200 -1000 1000 200

##################################################################################
# "Decay" block defines how each R1rho value is simulated by simulating decaying
#   magnetization as a function of time given parameters describing the chemical
#   exchange between 2/3 species.
# Decay is assumed to be monoexponential, and simulated R1rho values are given
#   by the monoexponential fit of decaying magnetization.
# Note: This assumption can be violated under some conditions, where decay
#       can be bi-exponential or other (not take in to account).
# Additionally, intensity values can be noise corrupted to give a noise
#   corrupted R1rho value originating from N-number of corrupted monoexponential
#   fits. This is approximating how we derive R1rho experimentally and its error.
#---------------------------------------------------------------------------------
# - 'vdlist' a number of delay points to simulate decaying magnetization over.
#     Col2: Lowest delay in seconds (usually 0)
#   Col3: Longest delay in seconds (>0.1 is good, but can use anything)
#   Col4: Number of delays between low and high
# - 'Read' defines a delay list to read in. This is any text file where each row
#   is a delay given in seconds (e.g. vdlist).
#   If commented out, it will not be read in. If given, it will be comined with
#   delay values simulated with the 'vdlist' command below.
# - 'PlotDec' can be 'yes' or 'no'. If 'yes', then it will plot the
#   simulated decay for each SLP/offset combination along with
#   the best-fit line for the R1rho value at that point.
#   WARNING: This can take a long time if you are simulating lots of data
# - 'Error' defines noise corruption value for simulated magnetization
#   at each time point. E.g. 0.02 would be 2%% noise corruption.
#   Error here translates to error in R1rho by simulating N=MCNum of
#     noise-corrupted monoexponential decays and fitting them and
#     calculating the error in R1rho from the distribution of fitted
#     R1rhos (error = sigma of gaussian distribution of fitted R1rhos)
# - 'MCNum' defines how many noise-corrupted decays to simulate and fit.
#     WARNING: This can take a long time if you are simulating a lot of data.
##################################################################################
+
Decay
vdlist 0.0 0.25 51
#Read delays
PlotDec no
Error 0.0
MCNum 500

##################################################################################
# "Plot" block lets you specify how to plot your simulated/real data.
#---------------------------------------------------------------------------------
# - 'Plot' can be 'line', 'symbol', or 'both'.
#   'Line' will plot a simulated line of R1rho values
#   'Symbol' will plot simulated R1rhos as symbol types defined below
#   'Both' with plot symbols over simulated lines
# - 'Line' defines the style of the line plot.
#   Col2: Type of line, see:
#   http://matplotlib.org/examples/lines_bars_and_markers/line_styles_reference.html
#      -   -.  --  or  :
#     Col3: Line-width, in pixels
# - 'Symbol' defines the style of the symbol plot.
#   Col2: Type of symbol, see: http://matplotlib.org/api/markers_api.html
#     Too many to list, but default is a filled circle: o
#   Col3: Size of symbol (pixels)
# - 'Overlay' defines how you plot data overlaid on simulation
# - 'OType' type of data to overlay, real or overlay.
# - 'OLine' line type for overlay
# - 'OSymbol' symbol type for overlay
# - 'Size' defines the plot width and height in inches
# - '(R1p/R2eff/On)_x/y' define the lower and upper limits of the respective axes
#   Comment out to let them be automatically defined.
#   Alternatively, set one or both values to 'None' to let the program
#   automatically define the limit of the lower/upper bounds, individually
#   e.g. 'R1p_x None 1000' would let lower x-axis limits be automatically
#   defined, but the upper limit would be set to 1000
# - 'Axis_FS' sets the axes numbers font sizes, X and Y axes, respectively
# - 'LabelFS' sets the X and Y axes labels font sizes
##################################################################################
+
Plot line
Line - 2
Symbol o 13
Overlay line
OType sim
OLine -- 2
OSymbol . 13
Size 10 8
#R1p_x None 1000
#R1p_y 0 100
#R2eff_x -1000 1000
#R2eff_y 0 100
On_x 0 None
#On_y 0 50
Axis_FS 32 32
Label_FS 32 32
Labels on
'''
        outPath = os.path.join(curDir, sys.argv[2])
        makeFolder(outPath)
        with open(os.path.join(outPath, "BMNS-SimParams.txt"), "w") as file:
            file.writelines(outstr)

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Generate Example Parameters Text file
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #  arg1 '-genpar' or '-genparsim' to read in simpars
    #  arg2 output directory
    #  arg3 optional name to put in example par
    #---------------------------------------------------
    elif "-genpar" in sys.argv[1].lower():
        # Set default initial guesses
        pars = {'lf': 150.784267,
                'te': 25.0,
                'alignmag': 'auto',
                'pb': 0.01,
                'pc': 0.0,
                'dwb': 3.0,
                'dwc': 0.0,
                'kexab': 3000.0,
                'kexac': 0.0,
                'kexbc': 0.0,
                'r1': 2.5,
                'r1b': 0.0,
                'r1c': 0.0,
                'r2': 16.0,
                'r2b': 0.0,
                'r2c': 0.0}

        if argc == 4:
            name = sys.argv[3]
        else:
            name = "FileName"
        # Read in simulated parameters as initial guess for fitting
        if sys.argv[1].lower() == "-genparsim":
            if argc == 4:
                name = "FileName"
                sim_p = os.path.join(curDir, sys.argv[3])
            elif argc == 5:
                name = sys.argv[3]
                sim_p = os.path.join(curDir, sys.argv[4])
            if os.path.isfile(sim_p):
                rd = pd.read_csv(sim_p, delimiter=",")
                pars = {x: rd[x][0] for x in pars}
                if pars['r1'] == pars['r1b'] == pars['r1c']:
                    pars['r1b'] = 0.0
                    pars['r1c'] = 0.0
                if pars['r2'] == pars['r2b'] == pars['r2c']:
                    pars['r2b'] = 0.0
                    pars['r2c'] = 0.0

        outstr = '''
##################################################################################
# Run the BMNS fitting program:
# > python BMNS.py -fit [BM Parameter Input File] [R1rho Data Directory] (Optional Output directory)
##################################################################################
# Define fitting setup.
# FitType: can be 'global' or 'local' or 'brute'
#          This is for global or local optimizations, not shared parameter fits.
#          'Brute' designates brute-force fixed calculations of the range of parameter
#                   space designated by lower/upper bounds on parameters.
#          - 'brutep' will generate plots at each increment point.
#             WARNING: This can take a LONG time.
#          'Bruteint' brute-forces parameter space by fitting intensities instead of
#                     R1p values
#
#          'Local' uses Levenberg-Marquardt semi-gradient descent/Gauss-Newton algorithm
#          - 'localint' fits intensities directly rather than R1p
#          'Global' uses the "Adaptive Memory Programming for Global Optimizations"
#                   algorithm, with the local 'L-BFGS-B' function, and polishes the
#                   global optimum with L-M.
# FitEqn: fit equation, "BM" for Bloch-McConnell or "Lag" for Laguerre 2-/3-state
# NumFits: is number of fit minima to find (ie. loop over fitting algorithm)
# RandomFitStart : can be 'Yes' or 'No'
#                  if 'Yes', randomly selects initial guess from parameter bounds
##################################################################################
+
FitType local
FitEqn BM
NumFits 1
RandomFitStart No

##################################################################################
# Define fit parameter data, data names, base freqs,
#  initial parameter guesses, and paramter lower and upper bounds.
#
# Add '+' to read in an additional set of parameters with given 'Name XYZ'
#   The 'Name' must match a .csv data file in given directory of the same name.
#
# Rows for parameters are as follows:
#  [Par name] [initial value] [lower bounds] [upper bounds] ([optional brute force number])
#
# If both lower and upper bounds are not given, they will be set to large values.
# '!' designates a fixed parameter that will not change throughout the fit.
# '*' designates a shared parameter that will be fitted for all data sets
#     also containing the 'x' flag, in a shared manner.
# '@' designates linear brute-force over parameter range of low to upper bounds
# '$' designates log brute-force over parameter range of low to upper bounds
#
# If R1b/c or R2b/c are fixed to 0, they will be shared with R1 / R2
#  e.g. "R1b! = 0.0" will be interpreted as "R1b = R1"
#
# lf = Larmor frequency (MHz) of the nucleus of interest
#      15N:   60.76302 (600) or  70.960783 (700)
#      13C: 150.784627 (600) or 176.090575 (700)
#
# (optional) rnddel = Fraction of data to be randomly deleted before fit
#                     e.g 'rnddel 0.1' would randomly delete 10pct of data
#
# Temp [Celsius or Kelvin] : Define temperature to calculate free energies
#
# AlignMag [Auto/Avg/GS]
#          Auto : calculates kex/dw and aligns mag depending on slow (gs) vs. fast (avg)
#          Avg : Aligns magnetization/projects along average effective field of GS/ESs
#          GS : Aligns magnetization along ground-state
#
# x-axis Lower Upper (Hz): Sets lower and upper x-axis limits for both plots
#   if not given, will automatically set them
#
# y-axis Lower Upper : Sets lower and upper y-axis limits for both plots
#   if not given, will automatically set them
#
# Trelax increment Tmax (seconds) : sets the increment delay and maximum relaxation
#  delay to simulate R1rho at.
#  Use caution with this flag, recommended that is remains commented out.
#  Array of delays is given as a linear spacing from 0 - Tmax in Tmax/Tinc number of points
#  If not defined, the program will calculate the best Tmax from the experimental
#   R1rho data.
##################################################################################

+
Name %s
lf %s
Temp %s
AlignMag %s
#Trelax 0.0005 0.5
#x-axis -2000 2000
#y-axis 0 50
pB %s 1e-6 0.5
pC! %s 1e-6 0.5
dwB %s -80 80
dwC! %s -80 80
kexAB %s 1.0 500000.0
kexAC! %s 1.0 500000.0
kexBC! %s 1.0 500000.0
R1 %s 1e-6 20.
R2 %s 1e-6 200.
R1b! %s
R2b! %s
R1c! %s
R2c! %s
''' % (name, pars['lf'], pars['te'], pars['alignmag'], pars['pb'],
       pars['pc'], pars['dwb'], pars['dwc'], pars['kexab'],
       pars['kexac'], pars['kexbc'], pars['r1'], pars['r2'],
       pars['r1b'], pars['r2b'], pars['r1c'], pars['r2c'])

        outPath = os.path.join(curDir, sys.argv[2])
        makeFolder(outPath)
        with open(os.path.join(outPath, "BMNS-Parameters.txt"), "w") as file:
            file.writelines(outstr)

    else: bme.help()

# Get command line arguments
curDir = os.getcwd()
argc = len(sys.argv)

# Run the actual program
Main()
