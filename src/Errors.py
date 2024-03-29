import sys, os

#########################################################################
# Check input arguments and handle errors within.
#   Returns nothing, but will exit program if not correct.
#########################################################################
def CheckErrArgs(curDir, argc, argv):

    exitBool = False # Bool to determine if program exits
    # Check if enough arguments were passed through command line
    #   to be able to run the program.
    if argc != 6:
        tstr = '''
  ERROR: %s arguments given to command line.
         Use -h for help.
  ------------------------------------------------
  arg1 '-error'
  arg2 Fit .csv file generated by BMNS.py -fit
  arg3 R1rho .csv data file with offsets,SLP,R1rho,R1rho error
  arg4 Output path to put error and fits.
  arg5 Numeric row numbers of fits to generate errors for.
       e.g. 1,3-5 would select 1,3,4,5 in fit.csv file
  ------------------------------------------------\n'''
        if argc < 6:
            tstr = tstr % "Too few"
        else:
            tstr = tstr % "Too many"
        exitBool = True

    # Now check that the fit file actually exist
    else:
        if not os.path.isfile(os.path.join(curDir, sys.argv[2])):
            print('''
  ERROR: Input fit.csv file does not exist. (%s)\n''' % os.path.join(curDir, sys.argv[2]))
            exitBool = True
        if not os.path.isfile(os.path.join(curDir, sys.argv[3])):
            print('''
  ERROR: Input R1rho data .csv file does not exist. (%s)\n''' % os.path.join(curDir, sys.argv[3]))
            exitBool = True
        # Check to make sure output directory is not a file
        if os.path.isfile(os.path.join(curDir, sys.argv[4])):
            print('''
  ERROR: Output path given has been defined as a file. (%s)\n''' % os.path.join(curDir, sys.argv[4]))
            exitBool = True
    # Terminate program if needed.
    if exitBool == True:
        print(tstr)
        sys.exit(-1)

#########################################################################
# Check input arguments and handle errors within.
#   Returns nothing, but will exit program if not correct.
#########################################################################
def CheckArgs(curDir, argc, argv):
    exitBool = False # Bool to determine if program exits
    # Check if enough arguments were passed through command line
    #   to be able to run the program.
    if 2 <= argc <= 3:
        print('''
  ERROR: Too few arguments given to command line.
        Use -h for help.
  ------------------------------------------------
  arg1 '-fit'
  arg2 Parameter Text File
       - See Example\ParExample.txt
  arg3 Parent directory of R1rho.csv data files
       corresponding to names in pars file.
       - Each data file is ordered: Offset (corrected, Hz), SLP (Hz), R1rho (s-1), R1rho error (s-1)
         If data file is .tab, assumes Offset<>SLP swap, and removes first column (Folder numbers)
         If data file has a header, removes header and first column (assumed to be Folder numbers)
  arg4 Output directory for fit data (Optional)
  ------------------------------------------------''')
        exitBool = True

    # If enough command line args were given, check that:
    #   1. Par input text exists
    #   2. Data directory exists
    else:
        if not os.path.isfile(os.path.join(curDir, sys.argv[2])):
            print('''
  ERROR: Input Parameter text file does not exist.''')
            exitBool = True
        if not os.path.isdir(os.path.join(curDir, sys.argv[3])):
            print('''
  ERROR: Input Data directory does not exist.''')
            exitBool = True
    # Determine if program needs to exit, then do so as needed.
    if exitBool == True:
        print("")
        sys.exit(-1)
#########################################################################
# Handle Given Errors and exit program
#   Takes in a bool that tells the program to exit or not
#   Also prints out an error message if given
#########################################################################
def HandleErrors(exitBool, message):
    if exitBool == True:
        print(message)
        sys.exit(-1)

#########################################################################
# Default help menu #
#########################################################################
def help():
    print("Usage is as follows:")
    print('''
  ######################################################
  #####  -fit : R1rho BM 2-/2-state Fitting Func.  #####
  ######################################################
  Takes in R1rho data and error (optional) and fits
   the data to the Bloch-McConnell numerical equations
   with different local and global fitting algorithms.

   arg1 '-fit'
   arg2 Parameter Text File
        - See Example\pExample.txt
   arg3 Parent directory of R1rho.csv data files
         corresponding to names in pars file.
       - Each data file is ordered: Offset (corrected, Hz), SLP (Hz), R1rho (s-1), R1rho error (s-1)
         If data file is .tab, assumes Offset<>SLP swap, and removes first column (Folder numbers)
         If data file has a header, removes header and first column (assumed to be Folder numbers)
   arg4 Output directory for fit data (Optional)

   >BMNS.py -fit [Parameter Text File] [Folder with data] [Output folder]\n''')

    print('''
  ###########################################################################
  #####  -fitmc : R1rho BM 2-/2-state Fitting with MC Error Estimation  #####
  ###########################################################################
  Takes in R1rho data and error (optional) and fits
   the data to the Bloch-McConnell numerical equations
   with different local and global fitting algorithms.

   arg1 '-fitmc'
   arg2 Parameter Text File
        - See Example\pExample.txt
   arg3 Parent directory of R1rho.csv data files
         corresponding to names in pars file.
       - Each data file is ordered: Offset (corrected, Hz), SLP (Hz), R1rho (s-1), R1rho error (s-1)
         If data file is .tab, assumes Offset<>SLP swap, and removes first column (Folder numbers)
         If data file has a header, removes header and first column (assumed to be Folder numbers)
   arg4 Output directory for fit data (Optional)
   arg5 Monte-Carlo Iteration number (optional)

   >BMNS.py -fit [Parameter Text File] [Folder with data] [Output folder] 100\n''')

    print('''
  ####################################################################
  #####   -thermo : Calculate free energies/indv rate constants  #####
  ####################################################################
  Takes in a BMNS full fit .csv (e.g. 'LocalFits_XYZ.csv)
  Will append calculated free energies and individual rate constants
    to the given fit file and rename it with a "thermo" suffix.
  Errors in calculations are propogated by linear error propogation theory
    using the Uncertainties Python package.

  >BMNS.py -thermo [fit.csv] [Temp (C or K)]\n''')

    print('''
  ####################################################################
  #####   -compare : Compares statistics .csv files to one another ###
  ####################################################################
  Takes in a list of BMNS Stats.csv files (e.g. 'LocalStats_XYZ.csv)
    More than 1. Compares each of them to one another to compute
    which model best fits the data.
  This assumes the underlying data for each model is IDENTICAL.
  Output is terminal text that describes the best model based on AIC/BIC
  values and relative weights to one another

  >BMNS.py -compare [LocalStats_1.csv LocalStats_2.csv (LocalStats_3.csv...)...]\n''')

    print('''
  ######################################################
  #####   -tab2csv : Convert tab file to csv file  #####
  ######################################################
  Takes in a tab file and converts to csv

  >BMNS.py -tab2csv [tab file]\n''')

    print('''
  ######################################################
  ### -genpar : Generates a parameter txt file       ###
  ######################################################
  Uses MC/Bootstrap approach to generate error in
  fitted parameters in given .csv file.

  >BMNS.py -genpar [output folder] [Name, optional]\n''')
