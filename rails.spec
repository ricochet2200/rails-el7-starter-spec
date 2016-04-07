Name:           <Fill this in>
Version:        %{_version}
Release:        1%{?dist}
Summary:        <Fill this in>
License:        <Fill this in>

# Some of the gems compile, and thus this can't be noarch
BuildArch:      x86_64
Group:          <Fill this in>
URL:            <git repository url>
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)


# What repository to pull the actual code from
%define git_repo <git repository url>
%define rails_home /var/www/

# You will always need these to roll your rails app into an rpm
BuildRequires: ruby rubygems rubygem-bundler ruby-devel  

# There is a fair chance you will need these as well.  Uncomment them as needed.
# There is a very high propability you will need to add more requirements here.  We are going to build gems and they
# have build requirements.  Pay attention to any error messages you get and try to figure out what rpms you need to install.
# `yum provides */<nameOfLib.lib>` can be very helpful
# BuildRequires: mariadb-devel gcc-c++ autoconf automake gcc

# Specifies to yum what packages are needed for this to install properly.  This assumes you us mariadb, change if needed.
Requires: mod_passenger httpd mariadb-server rubygem-bundler httpd-devel 

# We will add a user to run passenger.  Make sure we can do that.
Requires(pre): /usr/sbin/useradd, /usr/bin/getent /usr/sbin/usermod
Requires(postun): /usr/sbin/userdel

# rpmbuild will try to determin our requirements for us.  Sometimes it gets it wrong and breaks stuff.  If that happens, uncomment
# the next line and it will only require what you say (careful to get it right).
#AutoReqProv: no

#
# DIRS
# - Trying to follow Linux file system hierarchy
#
%define appdir %{rails_home}/%{name}
%define bindir %{rails_home}/%{name}/bin
%define configdir %{rails_home}/%{name}/config
%define logrotate /etc/logrotate.d/%{name}

%description
<Fill this in>

%prep
rm -rf ./%{name}
git clone %{url}
pushd

# Your branch name should match your version.  This should be based in as an arg to rpmbuild
git checkout %{version}
popd

%build
pushd

# This will download and build all gems in Gemfile so they will be packaged with this rpm
bundle install --without development --standalone

#
# ./public/assets
#
# Compile assets
rm -rf ./public/assets/*

# Create the assets now so they will be included in the rpm
bundle exec rake assets:precompile RAILS_ENV=production

popd

%install
# Create all the defined directories
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/%{appdir}
mkdir -p $RPM_BUILD_ROOT/%{configdir}
mkdir -p $RPM_BUILD_ROOT/etc/httpd/conf.d/
mkdir -p $RPM_BUILD_ROOT/etc/logrotate.d/

# Create the bundler config file so we use the standalone gems
mkdir $RPM_BUILD_ROOT/%{appdir}/.bundle
echo "BUNDLE_PATH: bundle" > $RPM_BUILD_ROOT/%{appdir}/.bundle/config
echo "BUNDLE_WITHOUT: development" >> $RPM_BUILD_ROOT/%{appdir}/.bundle/config
echo "BUNDLE_DISABLE_SHARED_GEMS: '1'" >> $RPM_BUILD_ROOT/%{appdir}/.bundle/config

# Start moving files into the proper place in the build root
pushd

#
# Config
#
mv ./config/ $RPM_BUILD_ROOT/%{appdir}
# This configures apache for this app
mv ./%{name}.conf $RPM_BUILD_ROOT/etc/httpd/conf.d/

#
# log
#
# Remove any non-production log files
rm -f log/*

# The extra files are the files that logrotate will make
# We make them here so that rpm will remove them on uninstall
touch log/production.log
touch log/production.log.1
touch log/production.log.2
touch log/production.log.3

#
# logrotate
#
mv logrotate $RPM_BUILD_ROOT/%{logrotate}

#
# Everything left goes in appdir
#
rm -rf tmp/
rm -rf test/
rm -rf mockups/
rm roll-rpm.sh
rm %{name}.spec

# You may need to add more files to delete

mv ./* $RPM_BUILD_ROOT/%{appdir}

popd

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,%{name},%{name},-)
%{appdir}

%config(noreplace) %{configdir}/database.yml

%attr(555,%{name},%{name}) %{bindir}

/etc/httpd/conf.d/%{name}.conf
%{logrotate}
%doc

%pre
# Create a user for this app to run under.
/usr/bin/getent group %{name} || /usr/sbin/groupadd %{name}

# There is a bug (https://github.com/phusion/passenger/issues/1740) that passenger must have the user
# have a home dir.  This is super lame.  We will create the home dir for now.  When this bug is fixed
# uncomment the correct command
#/usr/bin/getent passwd  %{name} || /usr/sbin/useradd --system --no-create-home -g  %{name}  %{name}

%post

cd /var/www/ %{name}
# You will probably need to replace %{name} with the name here
if [ $1 -eq 1 ]; then     # This is an install
    # Be really careful about not messing with this file if it exists. If it exists, there is a fair chance there is also a database
    # encrypted with the SECRET_KEY_BASE in it.  If it is deleted, we may suddenly find ourselves providing cracking services...
    if [ ! -f /var/www/%{name}/config/app_environment_variables.rb ]; then
        echo "ENV['SECRET_KEY_BASE']='`RAILS_ENV=production bin/rake secret`'" > /var/www/%{name}/config/app_environment_variables.rb
        echo "# Set the mysql root password in the line below"
        echo "ENV['DATABASE_PASSWORD']=''" >> /var/www/ %{name}/config/app_environment_variables.rb
        echo "ENV['GEM_HOME']='/var/www/ %{name}/bundle/ruby/gems'" >> /var/www/%{name}/config/app_environment_variables.rb
        echo "ENV['GEM_PATH']='/var/www/ %{name}/bundle/ruby/gems'" >> /var/www/%{name}/config/app_environment_variables.rb
    fi

    chmod 700 /var/www/%{name}/config/app_environment_variables.rb
    chown %{name}:%{name} /var/www/%{name}/config/app_environment_variables.rb
#else  # This is an update
fi

service httpd restart
service mariadb start

# rake db:set runs create, load, and seed the db
RAILS_ENV=production /usr/bin/bundle exec rake db:setup

if [ $1 -eq 1 ]; then     # This is an install

    # This is a script that helps secure the database
    # Documentation here: https://dev.mysql.com/doc/refman/5.6/en/mysql-secure-installation.htmla
    mysql_secure_installation

    echo
    echo "************************************************************************************"
    echo " If you set your root password, you will need to change ENV['DATABASE_PASSWORD'] in"
    echo " /var/www/%{name}/app_environment_variables.rb"
    echo "************************************************************************************"
    echo
fi

%postun
/usr/sbin/userdel %{name}
/usr/sbin/groupdel %{name}
