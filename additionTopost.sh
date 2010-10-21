rsync=`which rsync`
if [ -z "${rsync}" ]; then
	rsync="${part_mnt}/usr/bin/rsync"
fi
mount | grep sda2 | awk '{print $3 "/*"}' > ${part_mnt}/etc/rsync.excludes
${rsync} -avH --exclude-from=${part_mnt}/etc/rsync.excludes / 192.168.1.10::laclie/
