#!/usr/bin/env bash

set -x
set -e

C2URL=http://cvs2svn.tigris.org/svn/cvs2svn
C2REV=5465
CPATH=~/store/cvs
CROOTS="bufferman cvsdate cvsimport device diffie easycrt lost quickman rcsimport site_old stick tiger wces"
SROOT=https://russ.yanofsky.org/svn

# Checkout out cvs2svn script and apply changes to config.
git svn clone --user=guest --revision="$C2REV" "$C2URL"/trunk cvs2svn
(cd cvs2svn; git reset --hard; git apply) <<EOS
--- a/cvs2git-example.options
+++ b/cvs2git-example.options
@@ -519,15 +519,11 @@ ctx.retain_conflicting_attic_files = False
 # (name, email).  Please substitute your own project's usernames here
 # to use with the author_transforms option of GitOutputOption below.
 author_transforms={
-    'jrandom' : ('J. Random', 'jrandom@example.com'),
-    'mhagger' : 'Michael Haggerty <mhagger@alum.mit.edu>',
-    'brane' : (u'Branko Čibej', 'brane@xbc.nu'),
-    'ringstrom' : 'Tobias Ringström <tobias@ringstrom.mine.nu>',
-    'dionisos' : (u'Erik Hülsmann', 'e.huelsmann@gmx.net'),
-
-    # This one will be used for commits for which CVS doesn't record
-    # the original author, as explained above.
-    'cvs2git' : 'cvs2git <admin@example.com>',
+    '-' : (u'Russell Yanofsky', 'russ@yanofsky.org'),
+    'joe' : (u'Russell Yanofsky', 'russ@yanofsky.org'),
+    'russ' : (u'Russell Yanofsky', 'russ@yanofsky.org'),
+    'russell' : (u'Russell Yanofsky', 'russ@yanofsky.org'),
+    'pltgrp' : (u'PLT Group', 'russ@yanofsky.org'),
     }
 
 # This is the main option that causes cvs2git to output to a
@@ -568,7 +563,7 @@ run_options.set_project(
     # The filesystem path to the part of the CVS repository (*not* a
     # CVS working copy) that should be converted.  This may be a
     # subdirectory (i.e., a module) within a larger CVS repository.
-    r'test-data/main-cvsrepos',
+    r'$CPATH/xxx',
 
     # A list of symbol transformations that can be used to rename
     # symbols in this project.
EOS

# Convert CVS repositories
for R in $CROOTS; do
  perl -pi -e "s|'($CPATH)/.*?'|'\1/$R'|" cvs2svn/cvs2git-example.options
  rm -rf cvs2git-tmp "$R" "out/$R"
  cvs2svn/cvs2git --options=cvs2svn/cvs2git-example.options
  git init --bare "out/$R"
  cat cvs2git-tmp/git-blob.dat cvs2git-tmp/git-dump.dat | GIT_DIR="out/$R" git fast-import --force
done

# Create config file for subversion authors.
cat > authors <<EOF
russ = Russell Yanofsky <russ@yanofsky.org>
root = Russell Yanofsky <russ@yanofsky.org>
rey4 = Russell Yanofsky <russ@yanofsky.org>
httpd  = httpd  <>
cmpilato  = cmpilato  <>
(no author)  = (no author)  <>
gstein  = gstein  <>
jpaint  = jpaint  <>
akr  = akr  <>
timcera  = timcera  <>
pefu  = pefu  <>
lbruand  = lbruand  <>
uid99421  = uid99421  <>
jhenstridge  = jhenstridge  <>
maxb  = maxb  <>
dionisos  = dionisos  <>
guest  = guest  <>
svm = svm <>
EOF

# Convert subversion repositories.
for R in ~/store/svn/{rref,net,site,cfree,fbdb,cs4772-project} /mnt/hd/_tmp/viewvc-svnsync; do
    N="${R##*/}"
    if test "$N" = cfree; then TRUNK_OPT=; else TRUNK_OPT=-s; fi

    rm -rf git-svn-clone git-svn-bare
    if test "$N" = viewvc-svnsync; then
        N=viewvc
        git svn clone $TRUNK_OPT -A authors --revision=0:1487 --use-svnsync-props "file://$R" git-svn-clone
    elif test "$N" = rref; then
        git svn clone -A authors --rewrite-root="$SROOT/$N" -T trunk -b vendor/gcc "file://$R" git-svn-clone
        (
            cd git-svn-clone
            git for-each-ref refs/remotes/origin | while read SHA IDC REF; do
                if test "$REF" = refs/remotes/origin/current; then
                    git update-ref refs/remotes/origin/upstream "$SHA" ""
                    git update-ref -d "$REF" "$SHA"
                elif test "$REF" != refs/remotes/origin/trunk; then
                    git update-ref "${REF%/*}/tags/upstream-${REF##*/}" "$SHA" ""
                    git update-ref -d "$REF" "$SHA"
                fi
            done
        )
    else
        git svn clone $TRUNK_OPT -A authors --rewrite-root="$SROOT/$N" "file://$R" git-svn-clone
    fi

    # based on https://github.com/dpocock/sync2git/blob/master/sync2git
    mkdir git-svn-bare
    (
        cd git-svn-bare
        git init --bare
        git symbolic-ref HEAD refs/heads/trunk
    )
    (
        cd git-svn-clone
        git remote add bare ../git-svn-bare
        if test -n "$TRUNK_OPT"; then
            git config remote.bare.push 'refs/remotes/origin/*:refs/heads/*'
        else
            git config remote.bare.push 'refs/remotes/git-svn:refs/heads/trunk'
        fi
        git push bare
    )
    (
        cd git-svn-bare
        git for-each-ref --format='%(refname)' refs/heads/tags | \
            cut -d / -f 4 | \
            while read ref;
            do
                git tag "$ref" "refs/heads/tags/$ref"
                git branch -D "tags/$ref"
            done
    )
    mv -iv git-svn-bare "out/$N"
done

cp -a --reflink out out.0

# Create empty repository for twofish.
git init --bare out/twofish

# Apply patches on top of converted repositories.
OUT=$PWD/out
WORK=$PWD/patch-work
(
    cd ~/russ/2016/github/patches
    for R in *; do
        for P in "$R"/*.patch; do
            test -e "$P" || continue
            git clone "$OUT/$R" "$WORK"
            (
                cd "$WORK"
                git am --committer-date-is-author-date
                git push
            ) < $P
            rm -rf "$WORK"
        done
    done
)

# Repack repositories.
for R in out/*; do
    GIT_DIR="$R" git gc --prune=all
done
