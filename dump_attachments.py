#!/usr/bin/env python3
'''
    attachments
    ===========

    Dump all the attachments in an ENEX file,
    and export the attachment-less ENEX file to disk.
'''

# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <https://unlicense.org>

import argparse
import base64
import hashlib
import mimetypes
import os

from lxml import etree

parser = argparse.ArgumentParser(prog='attachments')
parser.add_argument(
    '-f',
    '--file',
    help='Specify the input ENEX file.',
    required=True
)
parser.add_argument(
    '-o',
    '--output-dir',
    help='Specify the output directory for the attachments.',
    required=True
)

def write_resource(outdir, resource, memo={}):
    '''Export the data from each resource.'''

    # Extract the data
    data = {}
    for child in resource:
        if child.tag == 'data':
            # Decode the contents and empty them (for our subsequent export).
            # `dumper` doesn't properly handle empty files, so we trick
            # it by having it use `\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09'.
            assert child.get('encoding') == 'base64'
            data['contents'] = base64.b64decode(child.text)
            child.text = 'AAECAwQFBgcICQ==';
        elif child.tag == 'mime':
            # Need the mime type in case there is no filename.
            data['mime'] = child.text
        elif child.tag == 'resource-attributes':
            # Only want the filename
            for attrib in child:
                if attrib.tag == 'file-name':
                    # Some filenames are not valid, so we replace any invalid
                    # characters here. We want it to work on Windows and Unix-like OSes.
                    data['filename'] = attrib.text.replace('/', '').replace('\\', '')

    # Check if the path is duplicated
    assert 'contents' in data
    has_filename = 'filename' in data
    if not has_filename:
        # Use the hexdigest to get a filename, with the proper extension.
        # The hexdigest is MD5, as described here.
        resource_hash = hashlib.md5(data['contents'])
        extension = mimetypes.guess_extension(data['mime'], strict=True)
        data['filename'] = f'{resource_hash.hexdigest()}{extension}'

    assert 'filename' in data
    path = os.path.join(outdir, data['filename'])

    # De-duplication check, since we might have redundant filenames.
    if os.path.exists(path):
        # Check if the hash256 is identical of the 2 files.
        new_hash = hashlib.sha256(data['contents'])
        old_hash = hashlib.sha256(open(path, 'rb').read())
        if new_hash.hexdigest() != old_hash.hexdigest():
            # Add (1) to the name, to ensure we have unique filenames.
            root, ext = os.path.splitext(data['filename'])
            filename = data['filename']
            data['filename'] = f'{root}{memo[filename]}{ext}'
            memo[filename] += 1
    else:
        memo[data['filename']] = 1

    # Now need to add the filename to the node.
    # We do this after any deduplication checks, since otherwise
    # we might get incorrect filenames.
    if not has_filename:
        nodes = [i for i in resource if i.tag == 'resource-attributes']
        if nodes:
            assert len(nodes) == 1
            attrib = nodes[0]
        else:
            # No resource-attributes, create it.
            attrib = etree.SubElement(resource, 'resource-attributes')

        # Now append the filename to the attrib element.
        filename = etree.SubElement(attrib, 'file-name')
        filename.text = data['filename']

    # Write the data
    with open(path, 'wb') as file:
        file.write(data['contents'])


def process_note(outdir, note):
    '''Process and individual note, processing all attachments.'''

    for child in note:
        if child.tag == 'resource':
            write_resource(outdir, child)


def main():
    '''Process the ENEX file and extract all resources.'''

    args = parser.parse_args()
    attachments_dir = os.path.join(args.output_dir, 'attachments')
    os.makedirs(attachments_dir, exist_ok=True)

    xml_parser = etree.XMLParser(huge_tree=True, strip_cdata=False)
    tree = etree.parse(args.file, parser=xml_parser)
    root = tree.getroot()
    for note in root:
        assert note.tag == 'note'
        process_note(attachments_dir, note)

    basename = os.path.basename(args.file)
    tree.write(os.path.join(args.output_dir, basename))

if __name__ == '__main__':
    main()
