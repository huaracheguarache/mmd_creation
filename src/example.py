from main import MMDfromThredds


mmd = MMDfromThredds(catalog_url='https://thredds.met.no/thredds/catalog/osisaf/met.no/ice/index/v2p2/nh/catalog.html',
                     save_directory='example_out')

# Will print valid and invalid CF Standard Names in Thredds files.
mmd.print_cfstdn()

# Will interactively prompt user to map the CF Standard Names with GCMDSK matches. When there are no good matches, or no
# matches at all you need to provide a GCMDSK match of your own. Mapping will be saved as a csv file in save_directory
# (in this case named 'example_out').
mmd.map_standard_names()

# Creates MMD files for each Thredds file in Thredds directory. Files will be saved in save_directory (in this case
# named 'example_out').
#mmd.create_mmds()
