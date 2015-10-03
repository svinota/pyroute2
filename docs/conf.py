try:
    import configparser
except ImportError:
    import ConfigParser as configparser

config = configparser.ConfigParser()
config.read('../setup.ini')

extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.inheritance_diagram']


inheritance_graph_attrs = {'rankdir': 'LR',
                           'ratio': 'auto'}
source_suffix = '.rst'
master_doc = 'index'
project = u'pyroute2'
copyright = u'2013, Peter V. Saveliev'

version = config.get('setup', 'version')
release = config.get('setup', 'release')

exclude_patterns = ['_build']
pygments_style = 'sphinx'

html_theme = 'default'
html_static_path = ['_static']
htmlhelp_basename = 'pyroute2doc'


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
