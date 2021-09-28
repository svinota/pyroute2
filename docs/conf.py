import pyroute2

extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.inheritance_diagram',
              'aafigure.sphinxext']


inheritance_graph_attrs = {'rankdir': 'LR',
                           'ratio': 'auto'}
source_suffix = '.rst'
master_doc = 'index'
project = u'pyroute2'
copyright = u'2013, Peter V. Saveliev'

release = pyroute2.__version__

exclude_patterns = ['_build']
pygments_style = 'sphinx'
autodoc_member_order = 'bysource'

html_theme = 'default'
html_static_path = ['_static']
htmlhelp_basename = 'pyroute2doc'
templates_path = ['_templates']


latex_elements = {}
latex_documents = [('index',
                    'pyroute2.tex',
                    u'pyroute2 Documentation',
                    u'Peter V. Saveliev',
                    'manual'), ]

man_pages = [('index',
              'pyroute2',
              u'pyroute2 Documentation',
              [u'Peter V. Saveliev'], 1), ]

texinfo_documents = [('index',
                      'pyroute2',
                      u'pyroute2 Documentation',
                      u'Peter V. Saveliev',
                      'pyroute2',
                      'One line description of project.',
                      'Miscellaneous'), ]


def setup(app):
    app.add_css_file('custom.css')
