#!/sbin/itype
# This is a i file, used by initng parsed by install_service

daemon sshd {
 require_network;
 exec daemon = /usr/sbin/sshd;
 pid_file = /var/run/sshd.pid;
 forks;
 daemon_stops_badly;
}
