# See the file LICENSE for redistribution information.
#
# Copyright (c) 2008 WiredTiger Software.
#	All rights reserved.
#
# $Id$
#
# Read the api file and output C for the Db/Env structures, getter/setter
# functions, and other API initialization.

import os, string, sys
from dist import api_load, compare_srcfile

# Temporary file.
tmp_file = '__tmp'

# func_method_single --
#	Set methods to reference a single underlying function (usually an
#	error function).
def func_method_single(handle, method, config, rettype, func, args, f):
	f.write('\t' + handle + '->' + method +\
	    ' = (' + rettype + ' (*)\n\t    (' + handle.upper() + ' *')
	if not config.count('notoc'):
		f.write(', WT_TOC *')
	for l in args:
		f.write(', ' + l.split('/')[1].replace('@S', ''))
	f.write('))\n\t    __wt_' + handle + '_' + func + ';\n')

# func_method_std --
#	Set methods to reference their underlying function.
def func_method_std(handle, method, config, f):
	if config.count('local'):
		f.write('\t' + handle + '->' +\
		    method + ' = __wt_' + handle + '_' + method + ';\n')
	else:
		f.write('\t' + handle + '->' +\
		    method + ' = __wt_api_' + handle + '_' + method + ';\n')

# func_method_init --
#	Set methods to their initial state.
def func_method_init(handle, method, config, args, f):
	# If the open keyword is set, lock out the function until open.
	if config.count('open'):
		func_method_single(\
		    handle, method, config, 'int', 'lockout_open', args, f)
		return

	func_method_std(handle, method, config, f)

# func_method_open --
#	Set methods to reference their normal underlying function (after
#	the open method is called).
def func_method_open(handle, method, config, args, f):
	# If the open keyword is set, we need to reset the method.
	if config.count('open'):
		func_method_std(handle, method, config, f)

# func_method_lockout --
#	Set methods (other than destroy) to a single underlying error function.
def func_method_lockout(handle, method, config, args, f):
	# Skip the destroy method, it's the only legal method.
	if method.count('destroy'):
		return

	if config.count('methodV'):
		rettype = 'void'
	else:
		rettype = 'int'
	func_method_single(\
	    handle, method, config, rettype, 'lockout_err', args, f)

# func_decl --
#	Output method name and getter/setter variables for an include file.
def func_decl(handle, method, config, args, f):
	f.write('\n')

	# Output the setter variables.
	if config.count('getset') and method.count('set_'):
		for l in args:
			f.write('\t' + l.split\
			    ('/')[1].replace('@S', l.split('/')[0]) + ';\n')

	# Output the method variables.
	if config.count('methodV'):
		rettype = 'void'
	else:
		rettype = 'int'
	f.write('\t' + rettype + \
	    ' (*' + method + ')(\n\t    ' + handle.upper() + ' *')
	if not config.count('notoc'):
		f.write(', WT_TOC *')
	for l in args:
		f.write(', ' + l.split('/')[1].replace('@S', ''))
	f.write(');\n')

# func_getset --
#	Generate the actual getter/setter code for the API.
def func_getset(handle, method, config, args, f):
	if config.count('methodV'):
		rettype = 'void'
	else:
		rettype = 'int'
	
	s = 'static ' +\
	    rettype + ' __wt_' + handle + '_' + method + '(WT_TOC *toc)'
	f.write(s + ';\n')
	f.write(s + '\n{\n')
	f.write('\twt_args_' + handle + '_' + method  + '_unpack;\n')

	# Verify means call a standard verification routine because there are
	# constraints or side-effects on setting the value.  The setter fails
	# if the verification routine fails.
	if config.count('verify'):
		f.write('\n\tWT_RET((__wt_' +\
		    handle + '_' + method + '_verify(toc)));\n')
	else:
		f.write('\n')

	if config.count('getset') and method.count('get_'):
		for l in args:
			f.write('\t*(' + l.split('/')[0] + ')' +\
			    ' = ' + handle + '->' + l.split('/')[0] + ';\n')
	else:
		for l in args:
			f.write('\t' + handle + '->' +\
			    l.split('/')[0] + ' = ' + l.split('/')[0] + ';\n')
	f.write('\treturn (0);\n}\n\n')

# func_api_hdr --
#	Generate #defines and structures for the API.
op_cnt = 1
def func_api_hdr(handle, method, args, f):
	global op_cnt
	uv = handle.upper() + '_' + method.upper()
	lv = 'wt_args_' + handle + '_' + method

	f.write('\n#define\t' + 'WT_OP_' + uv + '\t' + str(op_cnt) + '\n')
	op_cnt += 1
	f.write('typedef struct {\n')
	for l in args:
		f.write('\t' +\
		    l.split('/')[1].replace('@S', l.split('/')[0]) + ';\n')
	f.write('} ' + lv + ';\n')

	f.write('#define\t' + lv + '_pack\\\n')
	sep = ''
	for l in args:
		f.write(sep + '\t' +\
		    'args.' + l.split('/')[0] + ' = ' + l.split('/')[0])
		sep = ';\\\n'
	f.write('\n')

	f.write('#define\t' + lv + '_unpack\\\n')
	f.write('\t' +\
	    handle.upper() + ' *' + handle + ' = toc->' + handle + ';\\\n')
	sep = ''
	for l in args:
		f.write(sep + '\t' +\
		    l.split('/')[1].replace('@S', l.split('/')[0]) +\
		    ' =\\\n\t    ((' +\
		    lv + ' *)(toc->argp))->' + l.split('/')[0])
		sep = ';\\\n'
	f.write('\n')

# func_api --
#	Generate the actual API code.
def func_api(handle, method, config, args, f):
	if config.count('methodV'):
		rettype = 'void'
	else:
		rettype = 'int'
	
	s = 'static ' + rettype + ' __wt_api_' +\
	    handle + '_' + method + '(\n\t' + handle.upper() + ' *' + handle
	if not config.count('notoc'):
		s += ',\n\tWT_TOC *toc'
	for l in args:
		s += ',\n\t' +\
		    l.split('/')[1].replace('@S', l.split('/')[0])
	s += ')'
	f.write(s + ';\n')
	f.write(s + '\n{\n')

	s = '\twt_args_' + handle + '_' + method
	f.write(s + ' args;\n\n')
	f.write(s + '_pack;\n\n')

	f.write('\twt_args_' + handle + '_toc_sched(WT_OP_' + 
	    handle.upper() + '_' + method.upper() + ');\n')
	f.write('}\n\n')

# func_api_switch --
#	Generate the switch for the API code.
def func_api_switch(handle, method, config, args, f):
	f.write('\tcase WT_OP_' + handle.upper() + '_' + method.upper() + ':\n')
	f.write('\t\t')
	if not config.count('methodV'):
		f.write('ret = ')
	f.write('__wt_' + handle + '_' + method + '(toc);\n')
	f.write('\t\tbreak;\n')

#####################################################################
# Read in the api.py file.
#####################################################################
arguments, config, flags = api_load()

#####################################################################
# Update api.h, the API header file.
#####################################################################
tfile = open(tmp_file, 'w')
tfile.write('/* DO NOT EDIT: automatically built by dist/api.py. */\n\n')

tfile.write('/*\n')
tfile.write(' * Do not clear the DB handle in the ENV schedule macro, we may be doing\n')
tfile.write(' * an ENV call from within a DB call.\n')
tfile.write(' */\n')
tfile.write('#define\twt_args_env_toc_sched(oparg)\\\n')
tfile.write('\ttoc->op = (oparg);\\\n')
tfile.write('\ttoc->argp = &args;\\\n')
tfile.write('\treturn (__wt_toc_sched(toc))\n')

tfile.write('#define\twt_args_db_toc_sched(oparg)\\\n')
tfile.write('\ttoc->op = (oparg);\\\n')
tfile.write('\ttoc->db = db;\\\n')
tfile.write('\ttoc->argp = &args;\\\n')
tfile.write('\treturn (__wt_toc_sched(toc))\n')

for i in sorted(filter(
    lambda _i: config[_i[0]].count('local') == 0, arguments.iteritems())):
	func_api_hdr(\
	    i[0].split('.')[0], i[0].split('.')[1], i[1], tfile)

tfile.close()
compare_srcfile(tmp_file, '../inc_posix/api.h')

#####################################################################
# Update api.c, the API source file.
#####################################################################
tfile = open(tmp_file, 'w')
tfile.write('/* DO NOT EDIT: automatically built by dist/api.py. */\n\n')
tfile.write('#include "wt_internal.h"\n\n')

#  Write the API functions.
for i in sorted(filter(
    lambda _i: config[_i[0]].count('local') == 0, arguments.iteritems())):
	func_api(\
	    i[0].split('.')[0], i[0].split('.')[1], config[i[0]], i[1], tfile)

# Write the Env/Db getter/setter functions.
for i in sorted(filter(
    lambda _i: config[_i[0]].count('getset'), arguments.iteritems())):
	func_getset(\
	    i[0].split('.')[0], i[0].split('.')[1], config[i[0]], i[1], tfile)

# Write the Env/Db method configuration functions.
tfile.write('void\n__wt_env_config_methods(ENV *env)\n{\n')
for i in sorted(filter(
    lambda _i: _i[0].count('env.'), arguments.iteritems())):
	func_method_init('env', i[0].split('.')[1], config[i[0]], i[1], tfile)
tfile.write('}\n\n')
tfile.write('void\n__wt_env_config_methods_open(ENV *env)\n{\n')
for i in sorted(filter(
    lambda _i: _i[0].count('env.'), arguments.iteritems())):
	func_method_open('env', i[0].split('.')[1], config[i[0]], i[1], tfile)
tfile.write('}\n\n')
tfile.write('void\n__wt_env_config_methods_lockout(ENV *env)\n{\n')
for i in sorted(filter(
    lambda _i: _i[0].count('env.'), arguments.iteritems())):
	func_method_lockout('env', i[0].split('.')[1], config[i[0]], i[1], tfile)
tfile.write('}\n\n')

tfile.write('void\n__wt_db_config_methods(DB *db)\n{\n')
for i in sorted(filter(
    lambda _i: _i[0].count('db.'), arguments.iteritems())):
	func_method_init('db', i[0].split('.')[1], config[i[0]], i[1], tfile)
tfile.write('}\n\n')
tfile.write('void\n__wt_db_config_methods_open(DB *db)\n{\n')
for i in sorted(filter(
    lambda _i: _i[0].count('db.'), arguments.iteritems())):
	func_method_open('db', i[0].split('.')[1], config[i[0]], i[1], tfile)
tfile.write('}\n')
tfile.write('void\n__wt_db_config_methods_lockout(DB *db)\n{\n')
for i in sorted(filter(
    lambda _i: _i[0].count('db.'), arguments.iteritems())):
	func_method_lockout('db', i[0].split('.')[1], config[i[0]], i[1], tfile)
tfile.write('}\n\n')

# Write the API switch.
tfile.write('void\n__wt_api_switch(WT_TOC *toc)\n{\n')
tfile.write('\tint ret;\n\n')
tfile.write('\tswitch (toc->op) {\n')
for i in sorted(filter(
    lambda _i: config[_i[0]].count('local') == 0, arguments.iteritems())):
	func_api_switch(\
	    i[0].split('.')[0], i[0].split('.')[1], config[i[0]], i[1], tfile)
tfile.write('\tdefault:\n')
tfile.write('\t\tret = WT_ERROR;\n')
tfile.write('\t\tbreak;\n')
tfile.write('\t}\n\n')
tfile.write('\ttoc->ret = ret;\n')
tfile.write('}\n')

tfile.close()
compare_srcfile(tmp_file, '../support/api.c')

#####################################################################
# Update wiredtiger.in file with Env and Db handle information.
#####################################################################
tfile = open(tmp_file, 'w')
skip = 0
for line in open('../inc_posix/wiredtiger.in', 'r'):
	if skip:
		if line.count('Env handle api section: END') or \
		    line.count('Db handle api section: END') or \
		    line.count('WT_TOC handle api section: END'):
			tfile.write('\t/*\n' + line)
			skip = 0
	else:
		tfile.write(line)
	if line.count('Env handle api section: BEGIN'):
		skip = 1
		tfile.write('\t */')
		for i in sorted(filter(
		    lambda _i: _i[0].count('env.'), arguments.iteritems())):
			func_decl('env', i[0].split('.')[1],
			    config[i[0]], arguments[i[0]], tfile)
	elif line.count('Db handle api section: BEGIN'):
		skip = 1
		tfile.write('\t */')
		for i in sorted(filter(
		    lambda _i: _i[0].count('db.'), arguments.iteritems())):
			func_decl('db', i[0].split('.')[1],
			    config[i[0]], arguments[i[0]], tfile)
	elif line.count('WT_TOC handle api section: BEGIN'):
		skip = 1
		tfile.write('\t */')
		for i in sorted(filter(
		    lambda _i: _i[0].count('wt_toc.'), arguments.iteritems())):
			func_decl('wt_toc', i[0].split('.')[1],
			    config[i[0]], arguments[i[0]], tfile)

tfile.close()
compare_srcfile(tmp_file, '../inc_posix/wiredtiger.in')

os.remove(tmp_file)
