"""Parsers for manually downloaded raw files (SIPRI, OpenSanctions, GDELT CSVs).

Each parser takes file-like input and returns a tidy pandas DataFrame;
they are deliberately tolerant of the metadata banners and column-name
drift these published files have between releases.
"""
