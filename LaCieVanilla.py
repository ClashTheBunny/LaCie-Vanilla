#!/usr/bin/env python
import pylzma
from cStringIO import StringIO
import tarfile
import sys, os, re
import hashlib
import struct

# set this if you don't have a ~/.ssh/id_[dr]sa.pub
ssh_key="""Your keys here
"""

try:
	keyfh = open(os.path.expanduser("~/.ssh/id_dsa.pub"),'rb')
except:
	try:
		keyfh = open(os.path.expanduser("~/.ssh/id_rsa.pub"),'rb')
	except:
		pass
	else:
		ssh_key=keyfh.read()
else:
	ssh_key=keyfh.read()

if ssh_key=="""Your keys here
""":
	print "You must either edit the ssh_key variable at the top of this or have an id_[dr]sa.pub file in your home directory"
	sys.exit()

sshdi="""#!/sbin/itype
# This is a i file, used by initng parsed by install_service

service sshd/generate_keys {
 need = udev;
 env KEYGEN=/usr/bin/ssh-keygen;
 env RSA1_KEY=/etc/ssh/ssh_host_key;
 env RSA_KEY=/etc/ssh/ssh_host_rsa_key;
 env DSA_KEY=/etc/ssh/ssh_host_dsa_key;

 script start = {
  [ ! -s ${RSA1_KEY} ] && \
  ${KEYGEN} -q -t rsa1 -f ${RSA1_KEY} -C '' -N '' 2>&1 >/dev/null
  if [ ! -s ${RSA_KEY} ]
  then
  ${KEYGEN} -q -t rsa -f ${RSA_KEY} -C '' -N '' 2>&1 >/dev/null
  chmod 600 ${RSA_KEY}
  chmod 644 ${RSA_KEY}.pub
  fi
  if [ ! -s ${DSA_KEY} ]
  then
  ${KEYGEN} -q -t dsa -f ${DSA_KEY} -C '' -N '' 2>&1 >/dev/null
  chmod 600 ${DSA_KEY}
  chmod 644 ${DSA_KEY}.pub
  fi
 }
}

daemon sshd {
 require_network;
 need = sshd/generate_keys;
 exec daemon = /usr/sbin/sshd;
 pid_file = /var/run/sshd.pid;
 forks;
 daemon_stops_badly;
}
"""

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
for tarinfo in captar:
	#print tarinfo.name, "is", tarinfo.size
	if tarinfo.name == "repository/rootfs.tar.lzma":
		rootfslzma = captar.extractfile(tarinfo)

		sha1hl = hashlib.sha1()
		sha1hl.update(rootfslzma.read())
		oldLZMAsha1 = sha1hl.hexdigest()
		
		rootfslzma.seek(0)

		contents = rootfslzma.read(5)
		rootfslzma.read(8)
		contents += rootfslzma.read()
		rootfsTarFH = open("rootFS.orig.tar",'wb')
		rootfsTarFH.write(pylzma.decompress(contents))
		rootfsTarFH.close()
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
		# Add sshd.i
		tarinfoNew.size = len(sshdi)
		tarinfoNew.name = "etc/initng/sshd.i"
		tarinfoNew.mode = 436
		rootfstarA.addfile(tarinfoNew, StringIO(sshdi))
		# Add authorized_keys
		tarinfoNew.size = len(ssh_key)
		tarinfoNew.name = "root/.ssh/authorized_keys"
		tarinfoNew.mode = 384
		rootfstarA.addfile(tarinfoNew, StringIO(ssh_key))
		rootfstarA.close()
		rootfstarR = open("rootFS.orig.tar",'r')
		rootfstarString = rootfstarR.read()
		newLZMA = compress_compatible(rootfstarString)
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
