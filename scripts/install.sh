#!/usr/bin/env bash
# GEVENT: Taken from https://raw.githubusercontent.com/DRMacIver/hypothesis/master/scripts/install.sh

# Special license: Take literally anything you want out of this file. I don't
# care. Consider it WTFPL licensed if you like.
# Basically there's a lot of suffering encoded here that I don't want you to
# have to go through and you should feel free to use this to avoid some of
# that suffering in advance.

set -e
set -x


# Where installations go
BASE=${BUILD_RUNTIMES-$PWD/.runtimes}
PYENV=$BASE/pyenv
echo $BASE
mkdir -p $BASE


if [ ! -d "$PYENV/.git" ]; then
    rm -rf $PYENV
    git clone https://github.com/pyenv/pyenv.git $BASE/pyenv
else
    back=$PWD
    cd $PYENV
    # We don't fetch or reset after the initial creation;
    # doing so causes the Travis cache to need re-packed and uploaded,
    # and it's pretty large.
    # So if we need to incorporate changes from pyenv, either temporarily
    # turn this back on, or remove the Travis caches.
    # git fetch || echo "Fetch failed to complete. Ignoring"
    # git reset --hard origin/master
    cd $back
fi


SNAKEPIT=$BASE/snakepit

##
# install(exact-version, bin-alias, dir-alias)
#
# Produce a python executable at $SNAKEPIT/bin-alias
# having the exact version given as exact-version.
#
# Also produces a $SNAKEPIT/dir-alias/ pointing to the root
# of the python install.
##
install () {

    VERSION="$1"
    ALIAS="$2"
    DIR_ALIAS="$3"

    DESTINATION=$BASE/versions/$VERSION

    mkdir -p $BASE/versions
    mkdir -p $SNAKEPIT

    if [ ! -e "$DESTINATION" ]; then
        mkdir -p $SNAKEPIT
        mkdir -p $BASE/versions
        $BASE/pyenv/plugins/python-build/bin/python-build $VERSION $DESTINATION
    fi

    # Travis CI doesn't take symlink changes (or creation!) into
    # account on its caching, So we need to write an actual file if we
    # actually changed something. For python version upgrades, this is
    # usually handled automatically (obviously) because we installed
    # python. But if we make changes *just* to symlink locations above,
    # nothing happens. So for every symlink, write a file...with identical contents,
    # so that we don't get *spurious* caching. (Travis doesn't check for mod times,
    # just contents, so echoing each time doesn't cause it to re-cache.)

    # Overwrite an existing alias
    ln -sf $DESTINATION/bin/python $SNAKEPIT/$ALIAS
    ln -sf $DESTINATION $SNAKEPIT/$DIR_ALIAS
    echo $VERSION $ALIAS $DIR_ALIAS > $SNAKEPIT/$ALIAS.installed
    $SNAKEPIT/$ALIAS --version
    # Set the PATH to include the install's bin directory so pip
    # doesn't nag.
    PATH="$DESTINATION/bin/:$PATH" $SNAKEPIT/$ALIAS -m pip install --upgrade pip wheel virtualenv
    ls -l $SNAKEPIT

}


for var in "$@"; do
    case "${var}" in
        2.7)
            install 2.7.16 python2.7 2.7.d
            ;;
        3.5)
            install 3.5.6 python3.5 3.5.d
            ;;
        3.6)
            install 3.6.8 python3.6 3.6.d
            ;;
        3.7)
            install 3.7.2 python3.7 3.7.d
            ;;
        pypy2.7)
            install pypy2.7-7.1.0 pypy2.7 pypy2.7.d
            ;;
        pypy3.6)
            install pypy3.6-7.1.0 pypy3.6 pypy3.6.d
            ;;
    esac
done
