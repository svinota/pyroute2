import pyroute2

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.inheritance_diagram',
    'aafigure.sphinxext',
    'code_include.extension',
]

aafig_format = {'html': 'svg', 'man': None}

inheritance_graph_attrs = {'rankdir': 'LR', 'ratio': 'auto'}
source_suffix = '.rst'
master_doc = 'index'
project = u'pyroute2'
copyright = u'Peter Saveliev and PyRoute2 team'

release = pyroute2.__version__

exclude_patterns = ['_build']
pygments_style = 'sphinx'
autodoc_member_order = 'bysource'

html_theme = 'default'
html_static_path = ['_static']
html_js_files = ['fixup.js']
html_css_files = ['custom.css']
htmlhelp_basename = 'pyroute2doc'
templates_path = ['_templates']


man_pages = [
    (
        'pyroute2-cli',
        'pyroute2-cli',
        'pyroute2 command line interface',
        ['Peter Saveliev'],
        1,
    ),
    (
        'pyroute2-dhcp-client',
        'pyroute2-dhcp-client',
        'pyroute2 dhcp client',
        ['Peter Saveliev'],
        1,
    ),
]
