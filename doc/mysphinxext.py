from __future__ import print_function
from sphinx.ext.autodoc import cut_lines
from sphinx.ext import intersphinx
from docutils import nodes

noisy = 0
message_cache = set()


def missing_reference(app, env, node, contnode):
    """Search the index for missing references.
    For example, resolve :class:`Event` to :class:`Event <gevent.event.Event>`"""
    # XXX methods and functions resolved by this function miss their ()

    if intersphinx.missing_reference(app, env, node, contnode) is not None:
        # is there a better way to give intersphinx a bigger priority?
        return

    env = app.builder.env

    type = node['reftype']
    target = node['reftarget']
    modname = node.get('py:module')
    classname = node.get('py:class')

    if modname and classname:
        return

    def new_reference(refuri, reftitle):
        newnode = nodes.reference('', '')
        newnode['refuri'] = refuri
        newnode['reftitle'] = reftitle
        newnode['py:class'] = 'external-xref'
        newnode['classname'] = 'external-xref'
        newnode.append(contnode)
        msg = 'Resolved missing-reference: :%5s:`%s` -> %s' % (type, target, refuri)
        if noisy >= 1 or msg not in message_cache:
            print(msg)
            message_cache.add(msg)
        return newnode

    if noisy >= 1:
        print('Looking for %s' % [type, target, modname, classname])
        print(node)

    for docname, items in env.indexentries.items():
        if noisy >= 2:
            print(docname)
        for (i_type, i_string, i_target, i_aliasname) in items:
            if noisy >= 3:
                print('---', [i_type, i_string, i_target, i_aliasname])
            if i_aliasname.endswith(target):
                stripped_aliasname = i_aliasname[len(docname):]
                if stripped_aliasname:
                    assert stripped_aliasname[0] == '.', repr(stripped_aliasname)
                    stripped_aliasname = stripped_aliasname[1:]
                    if stripped_aliasname == target:
                        if noisy >= 1:
                            print('--- found %s %s in %s' % (type, target, i_aliasname))
                        return new_reference(docname + '.html#' + i_aliasname, i_aliasname)

    if type == 'mod':
        modules = [x for x in env.indexentries.keys() if x.startswith('gevent.')]
        target = 'gevent.' + target
        if target in modules:
            return new_reference(target + '.html', target)


def setup(app):
    app.connect('missing-reference', missing_reference)
    app.connect('autodoc-process-docstring', cut_lines(2, what=['module']))
