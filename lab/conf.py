import pyroute2

source_suffix = '.rst'
master_doc = 'index'

project = 'lab.pyroute2'
copyright = '2022, Peter Saveliev'
author = 'Peter Saveliev'

release = pyroute2.__version__


extensions = [
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


html_theme = 'default'
html_css_files = ['custom.css']
html_js_files = ['conf.js', 'lab.js', 'fixup.js']
html_static_path = ['_static']
