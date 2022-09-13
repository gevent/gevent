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

update_pyenv () {
    VERSION="$1"
    if [ ! -d "$PYENV/.git" ]; then
        rm -rf $PYENV
        git clone https://github.com/pyenv/pyenv.git $BASE/pyenv
    else
        if [ ! -f "$PYENV/plugins/python-build/share/python-build/$VERSION" ]; then
            echo "Updating $PYENV for $VERSION"
            back=$PWD
            cd $PYENV

            git fetch || echo "Fetch failed to complete. Ignoring"
            git reset --hard origin/master
            cd $back
        fi
    fi
}


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
        update_pyenv $VERSION
        # -Ofast makes the build take too long and times out Travis. It also affects
        # process-wide floating-point flags - see: https://github.com/gevent/gevent/pull/1864
        CFLAGS="-O1 -pipe -march=native" $BASE/pyenv/plugins/python-build/bin/python-build $VERSION $DESTINATION
    fi

    # Travis CI doesn't take symlink changes (or creation!) into
    # account on its caching, So we need to write an actual file if we
    # actually changed something. For python version upgrades, this is
    # usually handled automatically (obviously) because we installed
    # python. But if we make changes *just* to symlink locations above,
    # nothing happens. So for every symlink, write a file...with identical contents,
    # so that we don't get *spurious* caching. (Travis doesn't check for mod times,
    # just contents, so echoing each time doesn't cause it to re-cache.)

    # Overwrite an existing alias.
    # For whatever reason, ln -sf on Travis works fine for the ALIAS,
    # but fails for the DIR_ALIAS. No clue why. So we delete an existing one of those
    # manually.
    if [ -L "$SNAKEPIT/$DIR_ALIAS" ]; then
        rm -f $SNAKEPIT/$DIR_ALIAS
    fi
    ln -sfv $DESTINATION/bin/python $SNAKEPIT/$ALIAS
    ln -sfv $DESTINATION $SNAKEPIT/$DIR_ALIAS
    echo $VERSION $ALIAS $DIR_ALIAS > $SNAKEPIT/$ALIAS.installed
    $SNAKEPIT/$ALIAS --version
    $DESTINATION/bin/python --version
    # Set the PATH to include the install's bin directory so pip
    # doesn't nag.
    # Use quiet mode for this; PyPy2 has been seen to output
    # an error:
    #     UnicodeEncodeError: 'ascii' codec can't encode
    #     character u'\u258f' in position 6: ordinal not in range(128)
    # https://travis-ci.org/github/gevent/gevent/jobs/699973435
    PATH="$DESTINATION/bin/:$PATH" $SNAKEPIT/$ALIAS -m pip install -q --upgrade pip wheel virtualenv
    ls -l $SNAKEPIT
    ls -l $BASE/versions

}


for var in "$@"; do
    case "${var}" in
        2.7)
            install 2.7.17 python2.7 2.7.d
            ;;
        3.5)
            install 3.5.9 python3.5 3.5.d
            ;;
        3.6)
            install 3.6.10 python3.6 3.6.d
            ;;
        3.7)
            install 3.7.7 python3.7 3.7.d
            ;;
        3.8)
            install 3.8.2 python3.8 3.8.d
            ;;
        3.9)
            install 3.9.0 python3.9 3.9.d
            ;;
        pypy2.7)
            install pypy2.7-7.3.1 pypy2.7 pypy2.7.d
            ;;
        pypy3.6)
            install pypy3.6-7.3.1 pypy3.6 pypy3.6.d
            ;;
    esac
done
