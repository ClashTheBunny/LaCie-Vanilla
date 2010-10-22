#!/usr/bin/env python
"""
   Copyright 2010 Randall Mason

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License
"""
import pylzma
from cStringIO import StringIO
import tarfile
import sys, os, re
import hashlib
import struct

# set this if you don't have a ~/.ssh/id_[dr]sa.pub
ssh_key="""Your keys here
"""

KEYGEN="/usr/bin/ssh-keygen"

try:
	keyfh = open(os.path.expanduser("~/.ssh/id_dsa.pub"),'rb')
except:
	try:
		keyfh = open(os.path.expanduser("~/.ssh/id_rsa.pub"),'rb')
	except:
		try:
			keyfh = open("id_dsa.pub",'rb')
		except:
			pass
		else:
			ssh_key=keyfh.read()
			keyfh.close()
	else:
		ssh_key=keyfh.read()
		keyfh.close()
else:
	ssh_key=keyfh.read()
	keyfh.close()

if ssh_key=="""Your keys here
""":
	print "generating id_dsa and id_dsa.pub"
	argv = [KEYGEN,'-q','-tdsa','-fid_dsa']
	os.spawnv(os.P_WAIT,KEYGEN,argv)
	ssh_key = open("id_dsa.pub",'rb').read()

filesToAdd = {}

filesToAdd["authorized_keys"] = {}
filesToAdd["authorized_keys"]["string"] = ssh_key
filesToAdd["authorized_keys"]["len"] = len(ssh_key)
filesToAdd["authorized_keys"]["path"] = "root/.ssh/"
filesToAdd["authorized_keys"]["perms"] = int(0600)

sshkeys = {}
sshkeys['rsa1']="ssh_host_key"
sshkeys['rsa']="ssh_host_rsa_key"
sshkeys['dsa']="ssh_host_dsa_key"


for keyType in sshkeys.keys():
	argv = [KEYGEN,'-q','-t'+keyType,'-f'+sshkeys[keyType],'-C','','-N','']
	os.spawnv(os.P_WAIT,KEYGEN,argv)

	filesToAdd[sshkeys[keyType]] = {}
	filesToAdd[sshkeys[keyType]]["string"] = open(sshkeys[keyType],'rb').read()
	filesToAdd[sshkeys[keyType]]["len"] = len(filesToAdd[sshkeys[keyType]]["string"])
	filesToAdd[sshkeys[keyType]]["path"] = "etc/ssh/"
	filesToAdd[sshkeys[keyType]]["perms"] = int(0600)

	filesToAdd[sshkeys[keyType] + ".pub"] = {}
	filesToAdd[sshkeys[keyType] + ".pub"]["string"] = open(sshkeys[keyType] + ".pub",'rb').read()
	filesToAdd[sshkeys[keyType] + ".pub"]["len"] = len(filesToAdd[sshkeys[keyType] + ".pub"]["string"])
	filesToAdd[sshkeys[keyType] + ".pub"]["path"] = "etc/ssh/"
	filesToAdd[sshkeys[keyType] + ".pub"]["perms"] = int(0644)

	os.remove(sshkeys[keyType])
	os.remove(sshkeys[keyType] + ".pub")

pathOfFilesToReadIn = {
		"moduli":"etc/ssh/",
		"ssh_config":"etc/ssh/",
		"sshd_config":"etc/ssh/",
		"sshd.i":"etc/initng/"
		}

for file in pathOfFilesToReadIn.keys():
	filesToAdd[file] = {}
	filesToAdd[file]["string"] = open(os.path.dirname(sys.argv[0]) + os.sep + file,'rb').read()
	filesToAdd[file]["len"] = len(filesToAdd[file]["string"])
	filesToAdd[file]["path"] = pathOfFilesToReadIn[file]
	filesToAdd[file]["perms"] = int(0644)

def compress_compatible(data):
	c = pylzma.compressfile(StringIO(data))
	# LZMA header
	result = c.read(5)
	# size of uncompressed data
	result += struct.pack('<Q', len(data))
	# compressed data
	return result + c.read()

file=sys.argv[1]
print "Editing %s!" % file

#read entire file in
fh = open(file,'rb')
capsule = fh.read()
fh.close()
#find first <\/Capsule>\n and split on that
capre = re.compile("(.*)(</Capsule>)(.*)")
matches = capre.search(capsule)
if not matches:
	sys.exit()

capsuleFileXML = capsule[0:matches.end(0)+1]
capsuleFileTar = capsule[matches.end(0)+1:]

#untar second half
newTarFile = "newTarFile.tar"
captarNew = tarfile.open(newTarFile,'w')
captar = tarfile.open(fileobj=StringIO(capsuleFileTar))
captar.extractall()
postScriptUpdated = False
for tarinfo in captar:
	#print tarinfo.name, "is", tarinfo.size
	if tarinfo.name == "repository/rootfs.tar.lzma" or tarinfo.name == "repository/rootfs.tar.xz":
		rootfslzma = captar.extractfile(tarinfo)

		sha1hl = hashlib.sha1()
		sha1hl.update(rootfslzma.read())
		oldLZMAsha1 = sha1hl.hexdigest()
		
		rootfslzma.seek(0)

		contents = rootfslzma.read(5)
		rootfslzma.read(8)
		contents += rootfslzma.read()
		print "Unlzma'ing the rootfs...",
		rootfsTarFH = open("rootFS.orig.tar",'wb')
		rootfsTarFH.write(pylzma.decompress(contents))
		rootfsTarFH.close()
		print "Done unlzma'ing the rootfs!"
		rootfsTarFH = open("rootFS.orig.tar",'rb')
		rootfstarR = tarfile.open(fileobj=rootfsTarFH,mode='r')
		for rootfstarinfo in rootfstarR:
			#print rootfstarinfo.name, "is", rootfstarinfo.size
			if rootfstarinfo.name == "etc/initng/runlevel/default.runlevel":
				defaultRunLevel = rootfstarR.extractfile(rootfstarinfo).read()
				defaultRunLevel += "sshd\n"
				tarinfoNew = rootfstarinfo
				tarinfoNew.size = len(defaultRunLevel)
				break
		#rootfstar.extractall()
		rootfstarR.close()
		rootfsTarFH.close()
		rootfstarA = tarfile.open("rootFS.orig.tar",'a')
		rootfstarA.addfile(tarinfoNew, StringIO(defaultRunLevel))
		for file in filesToAdd.keys():
			print "Adding " + file
			tarinfoNew.size = filesToAdd[file]["len"]
			tarinfoNew.name = filesToAdd[file]["path"] + file
			tarinfoNew.mode = filesToAdd[file]["perms"]
			rootfstarA.addfile(tarinfoNew, StringIO(filesToAdd[file]["string"]))
		rootfstarA.close()
		rootfstarR = open("rootFS.orig.tar",'rb')
		rootfstarString = rootfstarR.read()
		print "lzma'ing it back up...",
		newLZMA = compress_compatible(rootfstarString)
		print "Done!"
		tarinfoNew = tarinfo
		tarinfoNew.size = len(newLZMA)
		captarNew.addfile(tarinfoNew, StringIO(newLZMA))
		sha1hl = hashlib.sha1()
		sha1hl.update(newLZMA)
		newLZMAsha1 = sha1hl.hexdigest()
	elif tarinfo.name == "description.xml":
		descxml = captar.extractfile(tarinfo)
		descxmlTI = tarinfo
		descxmlStr = descxml.read()
	elif tarinfo.name == "description.sha1":
		descsha = captar.extractfile(tarinfo)
		descshaTI = tarinfo
		descshaStr = descsha.read()
	elif tarinfo.name[:len("repository/post_")] == "repository/post_" and postScriptUpdated == False:
		print "updating post script"
		postScriptUpdated = True
		postScript = captar.extractfile(tarinfo).read()
		postScript += "\n" + open(os.path.dirname(sys.argv[0]) + os.sep + "additionTopost.sh",'rb').read()
		tarinfo.size = len(postScript)
		captarNew.addfile(tarinfo,StringIO(postScript))
	else:
		captarNew.addfile(tarinfo,captar.extractfile(tarinfo))
captar.close()

print "NewLZMASha1 =", newLZMAsha1
print "OldLZMASha1 =", oldLZMAsha1
descSha1Old = hashlib.sha1()
descSha1Old.update(descxmlStr)
descSha1OldStr = descSha1Old.hexdigest()
print "Old Desc.sha1:", descSha1OldStr
descxmlStrNew = re.sub(oldLZMAsha1,newLZMAsha1,descxmlStr)
descxmlStrNew = re.sub("1.2.6","1.2.7",descxmlStr)
descxmlTI.size = len(descxmlStrNew)
captarNew.addfile(descxmlTI,StringIO(descxmlStrNew))
descSha1New = hashlib.sha1()
descSha1New.update(descxmlStrNew)
descSha1NewStr = descSha1New.hexdigest()
print "New Desc.sha1:", descSha1NewStr
descshaTI.size = len(descSha1NewStr)
captarNew.addfile(descshaTI,StringIO(descSha1NewStr))
captarNew.close()

newcapsuleFH = open("newTarFile.capsule",'wb')
newcapsuleFH.write(descxmlStrNew)
newcapsuleFH.write(open(newTarFile,'rb').read())
newcapsuleFH.close()

#unlzma and untar repository/rootfs.tar.lzma with permissions
#edit files and add files (ssh mostly, check what's in the buffalo executables)
#tar and lzma new root (check compression info on the first lzma and copy it.)
#compute sha1 of new root and edit description.xml
#retar entire directry
#concatinate new description.xml with new tar
#upload to Network Space 2

#figure out difference between kernel and uImage one for update and one to run on? important if we build our own kernel. maybe uimage is a kexecboot or uboot type kernel.
