Packaging infrastucture
=======================

All the package-specific scripts, configs etc. should be placed
under `packages` directory. It is better to use distutils
tarball in packaging.

packages/RedHat
---------------

One common spec for all the RedHat flavours. To create RedHat
package for the current running distro, run `make rpm`.

NOTE: for python3 you should have python3-pkgversion-macros installed,
available both on Fedora and EPEL.
