import threddsclient
import pathlib
import xarray as xr
import requests
import re
import textwrap
import pandas as pd
import functools
from lxml import etree
import uuid
from datetime import datetime


class MMDfromThredds:
    def __init__(self, catalog_url: str, save_directory: str):
        self.tc_elements = [tc_element for tc_element in threddsclient.crawl(catalog_url)]
        self.save_directory = pathlib.Path(save_directory)
        pathlib.Path.mkdir(self.save_directory, exist_ok=True)

        opendap_urls = [tc_element.opendap_url() for tc_element in self.tc_elements]
        unique_standard_names = set()
        unique_long_names = set()

        for opendap_url in opendap_urls:
            ds = xr.open_dataset(opendap_url)
            for variable in list(ds.data_vars):
                try:
                    unique_standard_names.add(ds[variable].standard_name)
                except AttributeError:
                    try:
                        # Sometimes the variable is missing a standard name by mistake
                        unique_long_names.add(ds[variable].long_name)
                    except AttributeError:
                        pass

        self.valid_standard_names = set()
        self.invalid_standard_names = set()
        self.valid_long_names = set()
        self.invalid_long_names = set()

        for standard_name in unique_standard_names:
            try:
                requests.get(f'https://vocab.met.no/rest/v1/CFSTDN/lookup?label={standard_name}').raise_for_status()
            except requests.exceptions.HTTPError:
                self.invalid_standard_names.add(standard_name)
            else:
                self.valid_standard_names.add(standard_name)

        for long_name in unique_long_names:
            try:
                requests.get(f'https://vocab.met.no/rest/v1/CFSTDN/lookup?label={long_name}').raise_for_status()
            except requests.exceptions.HTTPError:
                self.invalid_long_names.add(long_name)
            else:
                self.valid_long_names.add(long_name)

    def print_cfstdn(self, include_long_names=False):
        print('Valid CFSTDNs (standard names):')
        if len(self.valid_standard_names) > 1:
            for valid_standard_name in self.valid_standard_names:
                print(valid_standard_name)
        else:
            print('No valid standard names!')
        print('\n')

        print('Invalid CFSTDNs (standard names):')
        if len(self.invalid_standard_names) > 1:
            for invalid_standard_name in self.invalid_standard_names:
                print(invalid_standard_name)
        else:
            print('No invalid standard names!')
        print('\n')

        if include_long_names:
            print('Valid CFSTDNs (long names):')
            if len(self.valid_long_names) > 1:
                for valid_long_name in self.valid_long_names:
                    print(valid_long_name)
            else:
                print('No valid long names!')
            print('\n')

            print('Invalid CFSTDNs (long names):')
            if len(self.invalid_long_names) > 1:
                for invalid_long_name in self.invalid_long_names:
                    print(invalid_long_name)
            else:
                print('No invalid long names!')

    def __take_gcmdsk_input(self, message: str) -> str:
        while True:
            gcmdsk = input(message)

            try:
                requests.get(f'https://vocab.met.no/rest/v1/GCMDSK/lookup?label={gcmdsk}').raise_for_status()
            except requests.exceptions.HTTPError:
                print(f'The provided GCMDSK label does not exist! Please check that the syntax is correct.')
                continue

            break

        return gcmdsk

    def map_standard_names(self, ignore_names: list | None = None, include_long_names=False):
        if include_long_names:
            standard_names = self.valid_standard_names
            standard_names.union(self.invalid_standard_names)
            standard_names.union(self.valid_long_names)
            standard_names.union(self.invalid_long_names)
            standard_names = sorted(standard_names)
        else:
            standard_names = self.valid_standard_names
            standard_names.union(self.invalid_standard_names)
            standard_names = sorted(standard_names)

        if ignore_names:
            for ignore_name in ignore_names:
                standard_names.remove(ignore_name)

        cfstdn_to_gcmdsk_mapping = {}
        for standard_name in standard_names:
            try:
                requests.get(f'https://vocab.met.no/rest/v1/CFSTDN/lookup?label={standard_name}').raise_for_status()
            except requests.exceptions.HTTPError:
                raise SyntaxError(f'The following standard_name is not in the CFSTDN vocabulary: {standard_name}')

            url = (f'https://vocab.met.no/rest/v1/CFSTDN/mappings?external=false&uri=https://vocab.met.no/CFSTDN/'
                   f'{standard_name}')
            response = requests.get(url).json()

            gcmdsk_matches = []
            for mapping in response['mappings']:
                if 'toScheme' in mapping and 'https://vocab.met.no/GCMDSK' in mapping['toScheme']['uri']:
                    match_type = mapping['type'][0].replace('skos:', '')
                    uri = mapping['to']['memberSet'][0]['uri']
                    gcmdsk_label = mapping['prefLabel']

                    gcmdsk_info = requests.get(f'https://vocab.met.no/rest/v1/GCMDSK/mappings?uri='
                                               f'{uri}&lang=en&clang=en').json()
                    gcmdsk_description = re.search(r'(?<=skos:definition\":{\"lang\":\"en\",\"value\":\")'
                                                   r'.*?(?="})', gcmdsk_info['graph']).group()

                    gcmdsk_matches.append((match_type, uri, gcmdsk_label, gcmdsk_description))

            if gcmdsk_matches:
                print(f'GCDMSK matches for CFSTDN {standard_name}:')

                print('-' * 120)
                for i, gcmdsk_match in enumerate(gcmdsk_matches, 1):
                    print(f'{"Index":11}: {i}')
                    print(f'{"Match type":11}: {gcmdsk_match[0]}')
                    print(f'{"URI":11}: {gcmdsk_match[1]}')
                    print(f'{"GCMDSK":11}: {gcmdsk_match[2]}')
                    print(textwrap.fill(f'{"Definition":11}: {gcmdsk_match[3]}', width=120,
                                        subsequent_indent=f'{"":13}'))
                    print('-' * 120)

                while True:
                    index = input('Please type in an index of one of the selections or the number 0 if you want to '
                                  'provide a custom GCMDSK: ')

                    try:
                        index = int(index)
                    except ValueError:
                        print(f'Invalid index! Index must be an integer value between 0 and {i}.')
                        continue

                    if index < 0 or index > i:
                        print(f'Invalid index! Index must be an integer value between 0 and {i}.')
                        continue

                    break

                if index == 0:
                    gcmdsk = self.__take_gcmdsk_input('Please provide a GCMDSK label: ')
                else:
                    gcmdsk = gcmdsk_matches[index - 1][2]

                print('\n')

            else:
                gcmdsk = self.__take_gcmdsk_input(f'No GCMDSK matches found for CFSTDN {standard_name}. '
                                                  f'Please provide one: ')
                print('\n')

            cfstdn_to_gcmdsk_mapping[standard_name] = gcmdsk

        df = pd.DataFrame.from_dict(cfstdn_to_gcmdsk_mapping, orient='index')
        df.to_csv(self.save_directory / 'mapping.csv', header=False)

    def create_mmds(self, access_constraint: str, operational_status: str, parent_id: str, collections: list,
                    abstract_name: str | None = None, time_coverage_start_name: str | None = None,
                    time_coverage_start_format: str | None = None, time_coverage_end_name: str | None = None,
                    time_coverage_end_format: str | None = None, iso_topic_category: str | None = None,
                    keywords_separator: str | None = None, geospatial_lat_max_name: str | None = None,
                    geospatial_lat_min_name: str | None = None, geospatial_lon_max_name: str | None = None,
                    geospatial_lon_min_name: str | None = None, investigator_name_label: str | None = None,
                    investigator_email_label: str | None = None, investigator_organisation_label: str | None = None,
                    activity_type: str | None = None, wms_url=False):

        def prepend(ns, tag):
            return f'{{{ns}}}{tag}'

        prepend_mmd = functools.partial(prepend, 'http://www.met.no/schema/mmd')
        prepend_xml = functools.partial(prepend, 'http://www.w3.org/XML/1998/namespace')

        gcmdsk_mapping_file = pd.read_csv(self.save_directory / 'mapping.csv', header=None)
        gcmdsk_mapping = dict(zip(gcmdsk_mapping_file[0], gcmdsk_mapping_file[1]))

        for tc_element in self.tc_elements:
            ds = xr.open_dataset(tc_element.opendap_url())

            etree.register_namespace('mmd', 'http://www.met.no/schema/mmd')
            root = etree.Element(prepend_mmd('mmd'))

            metadata_identifier = etree.SubElement(root, prepend_mmd('metadata_identifier'))
            idnamespace = "no.met.adc:"
            file_uuid = uuid.uuid5(uuid.NAMESPACE_URL, tc_element.url.replace('catalog.xml?dataset=', ''))
            metadata_identifier.text = f'{idnamespace}{file_uuid}'

            title = etree.SubElement(root, prepend_mmd('title'))
            title.attrib[prepend_xml('lang')] = 'en'
            title.text = ds.attrs['title']

            abstract = etree.SubElement(root, prepend_mmd('abstract'))
            abstract.attrib[prepend_xml('lang')] = 'en'
            if abstract_name:
                abstract.text = ds.attrs[abstract_name]
            else:
                abstract.text = ds.attrs['abstract']

            metadata_status = etree.SubElement(root, prepend_mmd('metadata_status'))
            metadata_status.text = 'Active'

            for collection in collections:
                collection_ = etree.SubElement(root, prepend_mmd('collection'))
                collection_.text = collection

            dataset_production_status = etree.SubElement(root, prepend_mmd('dataset_production_status'))
            dataset_production_status.text = 'Not available'

            last_metadata_update = etree.SubElement(root, prepend_mmd('last_metadata_update'))
            update = etree.SubElement(last_metadata_update, prepend_mmd('update'))
            creation_timestamp = etree.SubElement(update, prepend_mmd('datetime'))
            creation_timestamp.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            update_type = etree.SubElement(update, prepend_mmd('type'))
            update_type.text = 'Created'
            note = etree.SubElement(update, prepend_mmd('note'))

            temporal_extent = etree.SubElement(root, prepend_mmd('temporal_extent'))
            start_date = etree.SubElement(temporal_extent, prepend_mmd('start_date'))
            if time_coverage_start_name:
                time_coverage_start = ds.attrs[time_coverage_start_name]
            else:
                time_coverage_start = ds.attrs['time_coverage_start']

            if time_coverage_start_format:
                time_coverage_start = datetime.strptime(time_coverage_start, time_coverage_start_format)

            start_date.text = time_coverage_start
            end_date = etree.SubElement(temporal_extent, prepend_mmd('end_date'))

            if time_coverage_end_name:
                time_coverage_end = ds.attrs[time_coverage_end_name]
            else:
                time_coverage_end = ds.attrs['time_coverage_end']

            if time_coverage_end_format:
                time_coverage_end = datetime.strptime(time_coverage_end, time_coverage_end_format)

            end_date.text = time_coverage_end

            iso_topic_category_ = etree.SubElement(root, prepend_mmd('iso_topic_category'))
            if iso_topic_category:
                iso_topic_category_.text = iso_topic_category
            else:
                iso_topic_category_.text = ds.attrs['iso_topic_category']

            access_constraint_ = etree.SubElement(root, prepend_mmd('access_constraint'))
            access_constraint_.text = access_constraint

            use_constraint = etree.SubElement(root, prepend_mmd('use_constraint'))
            identifier = etree.SubElement(use_constraint, prepend_mmd('identifier'))
            identifier.text = 'CC-BY-4.0'
            resource = etree.SubElement(use_constraint, prepend_mmd('resource'))
            resource.text = 'http://spdx.org/licenses/CC-BY-4.0'

            operational_status_ = etree.SubElement(root, prepend_mmd('operational_status'))
            operational_status_.text = operational_status

            keywords = etree.SubElement(root, prepend_mmd('keywords'))
            keywords.attrib['vocabulary'] = 'None'

            if keywords_separator:
                for ds_keyword in ds.attrs['keywords'].split(keywords_separator):
                    keyword = etree.SubElement(keywords, prepend_mmd('keyword'))
                    keyword.text = ds_keyword.strip()
            else:
                for ds_keyword in ds.attrs['keywords'].split(','):
                    keyword = etree.SubElement(keywords, prepend_mmd('keyword'))
                    keyword.text = ds_keyword.strip()

            variables = list(ds.data_vars)

            cfstdns = set()

            for variable in variables:
                try:
                    standard_name = ds[variable].standard_name
                except AttributeError:
                    # Sometimes the standard_name is missing!
                    standard_name = ds[variable].long_name

                if standard_name in self.valid_standard_names:
                    cfstdns.add(standard_name)
                elif standard_name in self.valid_long_names:
                    cfstdns.add(standard_name)

            if len(cfstdns) >= 1:
                keywords = etree.SubElement(root, prepend_mmd('keywords'))
                keywords.attrib['vocabulary'] = 'CFSTDN'
                for cfstdn in sorted(cfstdns):
                    keyword = etree.SubElement(keywords, prepend_mmd('keyword'))
                    keyword.text = cfstdn

                resource = etree.SubElement(keywords, prepend_mmd('resource'))
                resource.text = 'https://vocab.nerc.ac.uk/standard_name/'

            keywords = etree.SubElement(root, prepend_mmd('keywords'))
            keywords.attrib['vocabulary'] = 'GCMDSK'

            all_names = self.valid_standard_names
            all_names.union(self.invalid_standard_names)
            all_names.union(self.valid_long_names)
            all_names.union(self.invalid_long_names)

            gcmdsks = set()

            for name in all_names:
                try:
                    existing_mapping = gcmdsk_mapping[name]
                except KeyError:
                    pass
                else:
                    gcmdsks.add(existing_mapping)

            for gcmdsk in sorted(gcmdsks):
                keyword = etree.SubElement(keywords, prepend_mmd('keyword'))
                keyword.text = gcmdsk

            resource = etree.SubElement(keywords, prepend_mmd('resource'))
            resource.text = 'https://gcmd.earthdata.nasa.gov/kms/concepts/concept_scheme/sciencekeywords'
            separator = etree.SubElement(keywords, prepend_mmd('separator'))
            separator.text = '>'

            geographic_extent = etree.SubElement(root, prepend_mmd('geographic_extent'))
            rectangle = etree.SubElement(geographic_extent, prepend_mmd('rectangle'))
            rectangle.attrib['srsName'] = 'EPSG:4326'

            north = etree.SubElement(rectangle, prepend_mmd('north'))
            if geospatial_lat_max_name:
                north.text = str(ds.attrs[geospatial_lat_max_name])
            else:
                north.text = str(ds.attrs['geospatial_lat_max'])

            south = etree.SubElement(rectangle, prepend_mmd('south'))
            if geospatial_lat_min_name:
                south.text = str(ds.attrs[geospatial_lat_min_name])
            else:
                south.text = str(ds.attrs['geospatial_lat_min'])

            east = etree.SubElement(rectangle, prepend_mmd('east'))
            if geospatial_lon_max_name:
                east.text = str(ds.attrs[geospatial_lon_max_name])
            else:
                east.text = str(ds.attrs['geospatial_lon_max'])

            west = etree.SubElement(rectangle, prepend_mmd('west'))
            if geospatial_lon_min_name:
                west.text = str(ds.attrs[geospatial_lon_min_name])
            else:
                west.text = str(ds.attrs['geospatial_lon_min'])

            personnel = etree.SubElement(root, prepend_mmd('personnel'))
            role = etree.SubElement(personnel, prepend_mmd('role'))
            role.text = 'Investigator'
            name = etree.SubElement(personnel, prepend_mmd('name'))
            if investigator_name_label:
                name.text = ds.attrs[investigator_name_label]
            else:
                name.text = ds.attrs['creator_name']

            email = etree.SubElement(personnel, prepend_mmd('email'))
            if investigator_email_label:
                email.text = ds.attrs[investigator_email_label]
            else:
                email.text = ds.attrs['creator_email']

            organisation = etree.SubElement(personnel, prepend_mmd('organisation'))
            if investigator_organisation_label:
                organisation.text = ds.attrs[investigator_organisation_label]
            else:
                organisation.text = ds.attrs['institution']

            def add_data_access(resource_text, type_text, description_text):
                data_access = etree.SubElement(root, prepend_mmd('data_access'))
                resource = etree.SubElement(data_access, prepend_mmd('resource'))
                resource.text = resource_text
                type_ = etree.SubElement(data_access, prepend_mmd('type'))
                type_.text = type_text
                description = etree.SubElement(data_access, prepend_mmd('description'))
                description.text = description_text

            if tc_element.download_url():
                add_data_access(tc_element.download_url(), 'HTTP',
                                'Direct download of datafile')

            if tc_element.opendap_url():
                add_data_access(tc_element.opendap_url(), 'OPeNDAP',
                                'OPeNDAP access to dataset')

            if wms_url:
                if tc_element.wms_url():
                    add_data_access(tc_element.wms_url(), 'OGC WMS',
                                    'OOGC WMS GetCapabilities URL')

            related_dataset = etree.SubElement(root, prepend_mmd('related_dataset'))
            related_dataset.attrib['relation_type'] = 'parent'
            related_dataset.text = parent_id

            related_information = etree.SubElement(root, prepend_mmd('related_information'))
            resource = etree.SubElement(related_information, prepend_mmd('resource'))
            resource.text = str(tc_element.url.replace('xml', 'html'))
            type_ = etree.SubElement(related_information, prepend_mmd('type'))
            type_.text = 'Dataset landing page'
            description = etree.SubElement(related_information, prepend_mmd('description'))
            description.text = 'Dataset landing page'

            activity_type_ = etree.SubElement(root, prepend_mmd('activity_type'))
            if activity_type:
                activity_type_.text = activity_type
            else:
                activity_type_.text = ds.attrs['activity_type']

            xsl_path = 'sort_mmd_according_to_xsd.xsl'
            xsd_path = 'mmd.xsd'

            xslt = etree.parse(xsl_path)
            sort_xml = etree.XSLT(xslt)
            root = sort_xml(root).getroot()

            xsd = etree.parse(xsd_path)
            validate = etree.XMLSchema(xsd)
            validate.assertValid(root)

            element_tree = etree.ElementTree(root)
            name = tc_element.name.replace('.nc', '.xml')
            element_tree.write(self.save_directory / name, pretty_print=True)
