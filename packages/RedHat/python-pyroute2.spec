%global pkgname pyroute2

Name: python-%{pkgname}
Version: 0.3.4
Release: 1%{?dist}
Summary: Pure Python netlink library
License: GPLv2+
Group: Development/Languages
URL: https://github.com/svinota/%{pkgname}

BuildArch: noarch
BuildRequires: python2-devel
Source: https://pypi.python.org/packages/source/p/pyroute2/pyroute2-%{version}.tar.gz

%description
PyRoute2 provides several levels of API to work with Netlink
protocols, such as Generic Netlink, RTNL, TaskStats, NFNetlink,
IPQ.

%prep
%setup -q -n %{pkgname}-%{version}

%build
# nothing to build

%install
%{__python} setup.py install --root $RPM_BUILD_ROOT

%files
%doc README* LICENSE
%{python_sitelib}/%{pkgname}*

%changelog
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

* Tue Jun 26 2013 Peter V. Saveliev <peet@redhat.com> 0.1.10-1
- fd and threads leaks fixed
- shutdown sequence fixed (release() calls)
- ipdb: interface removal
- ipdb: fail on transaction sync timeout

* Tue Jun 11 2013 Peter V. Saveliev <peet@redhat.com> 0.1.9-2
- fedpkg import fix

* Tue Jun 11 2013 Peter V. Saveliev <peet@redhat.com> 0.1.9-1
- several races fixed
- Python 2.6 compatibility issues fixed

* Thu Jun 05 2013 Peter V. Saveliev <peet@redhat.com> 0.1.8-1
- initial RH build

