#!/usr/bin/python

import errno
from optparse import OptionParser
import os
import random
import re
import stat
import shutil
import subprocess
import sys

# How many time to try to create a unique temp file before giving up.
MAX_TEMP_FILE_ATTEMPTS = 10

errorFiles = []    # List of files that had errors

class BadFile:
    '''
    Represents a bad file. Members are:
    bakBackupFile: the full path to the bad backup files
    filename: the name of the file relative to the day's archive root. Use this as the source.
    compressed: true if the file name ends in .bz2
    '''
    def __init__(self, badBackupFile):
	self.badBackupFile = badBackupFile
	(root, ext) =os.path.splitext(badBackupFile)
	self.compressed = ext == ".bzw"
	m = fileNamePattern.match(badBackupFile)
	self.filename = m.group(1)
	self.errors = []

    def path(self, prefix = None):
	''' 
	Prefix should not end in /
	'''
	return os.path.join(prefix, self.filename)

    def setError(self, error):
	print "Adding error %s to %s" % (error, self.filename)
	self.errors.append(error)

    def __str__(self):
	return self.badBackupFile

def setErrorFile(errorString):
    bf.setError(errorString)
    if len(bf.errors) == 1: 
	print "Appending new error"
	errorFiles.append(bf)
    

def copyFile(source, dest, changeDestPermission = False, liverun = True, logLevel = 1):
    ''' Using shutil.copy, copy source to dest. If you get EACCESS error
	when attempting to do so, changeDestPermission == True allows
	this to give the file write permissions for the current user
	before trying again, then change it back when finished.
	liverun: if false, just log, but don't actually do anything.
	This returns 0 if everything was correct, or a non-zero errorno if it couldn't do the copy
    '''
    destPermissions = os.stat(dest).st_mode
    # Modified permissions have write permission for the user
    # TODO this should be smarter, such as setting write permissions for the user only if the user owns the file
    modifiedDestPermissions = destPermissions | stat.S_IWUSR
    changedPermissions = False    	# set to true if you changed permissions
    retval = 0				# Return value for this function
    try:
	# 1. Change file permissions if you should and are allowed to.
    	if destPermissions != modifiedDestPermissions and changeDestPermission:
	    try:
    	        if logLevel > 1: print "Changing permissions from %o to %o on\n   %s" % (destPermissions, modifiedDestPermissions, dest)
	    	if liverun: os.chmod(dest, modifiedDestPermissions)
		changedPermissions = True
	    except IOError as (errno, strerror):
	    	print "ERROR: I/O error(%d), couldn't change permissions of %s to %o: %s" % \
			(errno, dest, modifiedDestPermissions, sterrror)
    	    except Exception as e:
	        print "ERROR: Couldn't change permissions to allow writing of %s: %s" % (dest, e)
	    # Continue executing even if errors because maybe the copy will work.
	# 2. Do the copy
	try:
    	    if logLevel > 0: print "Copy\n   from %s\n   to %s" % (source, dest)
            if liverun: shutil.copyfile(source, dest)
	except IOError as (errno, strerror):
	    retval = errno
	    print "ERROR: I/O error({0}) when copying file to {2}: {1}".format(errno, strerror, dest)
	    setErrorFile(strerror + " while copying file")
    	except Exception as e:
	    retval = errno
	    print "ERROR: Couldn't copy\n   from %s\n   to %s: " % (source, dest, e)
	    setErrorFile(str(e) + " while copying file")

    finally:
	# 3. Reset the permissions if you changed them.
	if changedPermissions:
	    try:
    	        if logLevel > 1: print "Restoring %o as permissions on\n   %s" % (destPermissions, dest)
	    	if liverun: os.chmod(dest, destPermissions)
	    except IOError as (errno, strerror):
		if retval == 0: retval = errno
	    	print "ERROR: I/O error(%d), probably failed to change permissions of %s back to %s: %s" % \
			(errno, dest, destPermissions, sterrror)
	    	setErrorFile(strerror + " while resetting permissions")
	    except Exception as e:
		if retval == 0: retval = errno
	    	print "ERROR: Probably failed to change permissions of %s back to %s: %s" % \
			(dest, destPermissions, e)
	    	setErrorFile(str(e) + " while resetting permissions")
    return retval
	

# Log level is 0 for nothing but errors, 1 is normal output, 2 is verbose

parser = OptionParser(usage = "%prog [options] checkBackupLog GoodFilesRootDir")
parser.add_option("-d", "--dryrun", action="store_false", dest="liverun",
    help="Dry run, print actions but don't perform them")
parser.add_option("-n", "--noerrorlist", action="store_false", dest="showErrorList",
    help="Don't print list of files that had errors.")
parser.add_option("-p", "--permissions", action="store_true", dest="canChangePermissions",
    help="Temporarily change write permissions on file so you can copy it.")
parser.add_option("-q", "--quiet", action="store_const", const=0, dest="logLevel",
    help="Print only errors")
parser.add_option("-v", "--verbose", action="store_const", const=2, dest="logLevel",
    help="Print extra information")
parser.set_defaults(showErrorList=True) # If true, print out list of files with errors when done.
parser.set_defaults(liverun=True)
parser.set_defaults(logLevel=1)
parser.set_defaults(canChangePermissions=False)
(options, args) = parser.parse_args()

if not options.liverun:
   print "Doing dry run. No changes made to files."

if len(args) < 2: 
    parse.print_usage();
    exit(-1);

logfile = args[0]
goodroot = args[1]

print "Reading from %s, good files at %s" % (logfile, goodroot)


errorPattern = re.compile("^ERROR.*<(.*)>$")
fileNamePattern = re.compile(".*/\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}/(.*)$")

badFiles = []

filecount = 1
errorfilecount = 0

with open(logfile) as f:
    for line in f:
	match = errorPattern.match(line)
	if match:
	    badFiles.append(BadFile(match.group(1)))

if options.logLevel > 0: print "Repairing %d bad files" % (len(badFiles))
		
for bf in badFiles:
    source = bf.path(goodroot)
    dest = bf.badBackupFile
    ''' If source ends in bz2 and isn't present, but the source without that prefix is present,
    then bzip2 to the folder, and copy it, deleting the uncompressed version'''
    (sourcehead, sourcetail) = os.path.split(source)
    (sourceroot, sourceext) = os.path.splitext(sourcetail)
    print "------- File %d ------" % (filecount)
    filecount = filecount + 1

    if options.logLevel > 1:
    	print "Sourcehead " + sourcehead
    	print "Sourcetail " + sourcetail
    	print "Sourceroot " + sourceroot
    	print "Sourceext " + sourceext

    if sourceext == ".bz2":
	# Must copy compressed file.

	(destdir, destfile) = os.path.split(dest)
	uncompressedsource = os.path.join(sourcehead, sourceroot)

	# Make up a random temporary file name. Make several attempts, 
	# then give up if you can't find an unused name.
	tempdest = os.path.join(destdir, str(random.randint(1,9999)) + "~" + sourceroot + ".bz2")
	if options.logLevel > 1: print "Try %d time to make temp file" % ( MAX_TEMP_FILE_ATTEMPTS)
	remainingTempFileAttempts = MAX_TEMP_FILE_ATTEMPTS - 1
	while os.path.exists(tempdest) and remainingTempFileAttempts > 0:
	    if options.logLevel > 1: print "Temp file already exists: %s" % (tempdest)
	    tempdest = os.path.join(destdir, str(random.randint(1,9999)) + "~" + sourceroot + ".bz2")
	    remainingTempFileAttempts = remainingTempFileAttempts - 1
	if os.path.exists(tempdest) and remainingTempFileAttempts == 0:
	    print "ERROR: Can't create temp file %s, something already has that name" % (tempdest)
	    continue
	if options.logLevel > 0: print "bzip2\n   from %s\n   to %s" % (uncompressedsource, tempdest)

	# tempdest now contains a temporary file name.

	r = -1	# Return code for file compression operation. 0 = everything ok

	# Create compressed file.
	if options.liverun:
	    try:
	    	with open(tempdest, 'w') as d:
	            r = subprocess.call(['bzip2', '--stdout', uncompressedsource], stdout=d)
	    except IOError as (errno, strerror):
	    	print "ERROR: I/O error({0}) when creating compressed file {2}: {1}".format(errno, strerror, tempdest)
	    	setErrorFile(strerror + " while opening and creating temp compressed file")
	    except Exception as e:
    	    	print "ERROR: Some exception when creating compressed file %s: %s" % (tempdest, e)
	    	setErrorFile(str(e) + " while opening and creating temp compressed file")

	# Copy compressed file over erroneous file.
	if r == 0 or not options.liverun:
	    copyFile(tempdest, dest, options.canChangePermissions, options.liverun, options.logLevel)
	else:
	    print "ERROR: Problems creating local compressed file %s, return code %d" % (tempdest, r)
	    setErrorFile("Compression return code " + str(r))

	# Remove that temporary compressed file.
	if options.logLevel > 0: print "Removing temp file %s" % (tempdest)
	if os.path.exists(tempdest) and options.liverun:
	    try: 
	    	os.remove(tempdest)
	    except IOError as (errno, strerror):
	    	print "ERROR: I/O error({0}) when removing {2}: {1}".format(errno, strerror, tempdest)
	    except Exception as e:
	    	print "ERROR: Some kind of problem removing temp file %s: " % (tempdest, e)

    else:
	# Easy case - just a straight file copy
	copyFile(source, dest, options.canChangePermissions, options.liverun, options.logLevel)

print options.showErrorList
if options.showErrorList:
    if options.logLevel > 0: print "Files not corrected because of errors:"
    for f in errorFiles:
	if len(f.errors) == 1:
	    print "%s: %s" % (f, f.errors[0])
	else:
	    print "%s:"
	    for e in f.errors:
	    	print "   %s" % (e)
