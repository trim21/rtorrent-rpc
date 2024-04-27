# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "rtorrent-rpc"
copyright = "2023, Trim21 <trim21me@gmail.com>"
author = "Trim21 <trim21me@gmail.com>"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "furo.sphinxext",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autodoc_type_aliases = {"Unknown": "Unknown"}

autodoc_member_order = "bysource"
autodoc_class_signature = "separated"
add_module_names = False

html_theme_options = {
    "source_edit_link": "https://github.com/trim21/rtorrent-rpc/blob/master/docs/{filename}",
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
