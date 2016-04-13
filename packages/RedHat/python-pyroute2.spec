%global srcname pyroute2
%global sum Pure Python netlink library

Name: python-%{srcname}
Version: 0.3.19
Release: 1%{?dist}
Summary: %{sum}
License: GPLv2+
Group: Development/Languages
URL: https://github.com/svinota/%{srcname}

BuildArch: noarch
BuildRequires: python2-devel python3-devel
Source: https://pypi.python.org/packages/source/p/pyroute2/pyroute2-%{version}.tar.gz

%description
PyRoute2 provides several levels of API to work with Netlink
protocols, such as Generic Netlink, RTNL, TaskStats, NFNetlink,
IPQ.

%package -n python2-%{srcname}
Summary: %{sum}
%{?python_provide:%python_provide python2-%{srcname}}

%description -n python2-%{srcname}
PyRoute2 provides several levels of API to work with Netlink
protocols, such as Generic Netlink, RTNL, TaskStats, NFNetlink,
IPQ.

%package -n python3-%{srcname}
Summary: %{sum}
%{?python_provide:%python_provide python3-%{srcname}}

%description -n python3-%{srcname}
PyRoute2 provides several levels of API to work with Netlink
protocols, such as Generic Netlink, RTNL, TaskStats, NFNetlink,
IPQ.


%prep
%setup -q -n %{srcname}-%{version}

%build
%py2_build
%py3_build

%install
%py2_install
%py3_install

%files -n python2-%{srcname}
%doc README* LICENSE.GPL.v2 LICENSE.Apache.v2
%{python2_sitelib}/%{srcname}*

%files -n python3-%{srcname}
%doc README* LICENSE.GPL.v2 LICENSE.Apache.v2
%{python3_sitelib}/%{srcname}*

%changelog
* Tue Apr  5 2016 Peter V. Saveliev <peter@svinota.eu> 0.3.19-1
- separate Python2 and Python3 packages
- MPLS lwtunnel support

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.15-2

- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild
* Fri Nov 20 2015 Peter V. Saveliev <peter@svinota.eu> 0.3.15-1
- critical NetNS fd leak fix

* Tue Sep  1 2015 Peter V. Saveliev <peter@svinota.eu> 0.3.14-1
- bogus rpm dates in the changelog are fixed
- both licenses added

* Tue Sep  1 2015 Peter V. Saveliev <peter@svinota.eu> 0.3.13-1
- BPF filters support
- MPLS routes support
- MIPS platform support
- multiple improvements on iwutil
- memory consumption improvements

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.3.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Jan  8 2015 Peter V. Saveliev <peter@svinota.eu> 0.3.4-1
- Network namespaces support
- Veth, tuntap
- Route metrics

* Fri Dec  5 2014 Peter V. Saveliev <peter@svinota.eu> 0.3.3-1
- Fix-ups, 0.3.3
- Bugfixes for Python 2.6

* Tue Nov 18 2014 Peter V. Saveliev <peter@svinota.eu> 0.3.2-1
- Update to 0.3.2

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.2.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Tue Mar 18 2014 Jiri Pirko <jpirko@redhat.com> - 0.2.7-1
- Update to 0.2.7

* Thu Aug 22 2013 Peter V. Saveliev <peet@redhat.com> 0.1.11-1
- IPRSocket threadless objects
- rtnl: tc filters improvements

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.1.10-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Wed Jun 26 2013 Peter V. Saveliev <peet@redhat.com> 0.1.10-1
- fd and threads leaks fixed
- shutdown sequence fixed (release() calls)
- ipdb: interface removal
- ipdb: fail on transaction sync timeout

* Tue Jun 11 2013 Peter V. Saveliev <peet@redhat.com> 0.1.9-2
- fedpkg import fix

* Tue Jun 11 2013 Peter V. Saveliev <peet@redhat.com> 0.1.9-1
- several races fixed
- Python 2.6 compatibility issues fixed

* Wed Jun 05 2013 Peter V. Saveliev <peet@redhat.com> 0.1.8-1
- initial RH build

