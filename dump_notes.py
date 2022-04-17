#!/usr/bin/env python3
'''
    attachments
    ===========

    Dump all the notes in an ENEX file inside the CDATA sections.
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
import re
import shutil
import subprocess
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

FILENAME_REGEX = re.compile(r'[<>:"/\\|?*]')

def extract_resource(resource):
    '''Extract data from a resource node.'''

    # Extract the raw data first.
    raw = {}
    for child in resource:
        if child.tag == 'data':
            # Need to calculate the MD5 of the text.
            assert child.get('encoding') == 'base64'
            contents = base64.b64decode(child.text)
            raw['hash'] = hashlib.md5(contents).hexdigest()
        elif child.tag == 'mime':
            # Need the mime type in case there is no filename.
            raw['mime'] = child.text
        elif child.tag == 'resource-attributes':
            # Only want the filename
            raw.update({i.tag: i.text for i in child})

    # Now, extract our processed data.
    data = {}
    md5_hash = raw['hash']
    hash_data = data.setdefault(md5_hash, {})
    hash_data['extension'] = mimetypes.guess_extension(raw['mime'], strict=True)
    if 'file-name' in raw:
        # Use the provided filename.
        hash_data['filename'] = f'{FILENAME_REGEX.sub("-", raw["file-name"])}'
    else:
        # No filename, have to use the hash.
        hash_data['filename'] = f'{md5_hash}{hash_data["extension"]}'

    return data


def process_note(outdir, note):
    '''Process and individual note, processing all attachments.'''

    raw = {}
    for child in note:
        if child.tag == 'title':
            raw['title'] = child.text
        elif child.tag == 'content':
            raw['content'] = child.text
        elif child.tag == 'resource':
            resource = raw.setdefault('resource', {})
            resource.update(extract_resource(child))

    # Now, we need to process the raw data.
    filename = f'{FILENAME_REGEX.sub("-", raw["title"])}.html'

    # Parse as HTML, and then process the HTML.
    html_parser = etree.HTMLParser()
    root = etree.fromstring(raw['content'].encode(), parser=html_parser)

    # Remove the `<en-note>` tag but keep children.
    body = root[0]
    en_note = body[0]
    body.remove(en_note)
    body.extend(en_note)

    # Change the `<en-media>` tags to `<img>` or similar.
    media_elements = root.xpath('//en-media')
    for element in media_elements:
        md5_hash = element.attrib.pop('hash')
        del element.attrib['type']
        resource = raw['resource'][md5_hash]
        uri = f'@attachment/{resource["filename"]}'
        if resource['extension'] in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
            # Embed an image.
            element.tag = 'img'
            element.attrib['src'] = uri
            element.attrib['alt'] = resource['filename']
        else:
            # Use a link tag.
            element.tag = 'a'
            element.attrib.clear()
            element.attrib['href'] = uri
            element.text = resource['filename']

    # Write out HTML to file.
    path = os.path.join(outdir, filename)
    html = etree.tostring(
        root,
        pretty_print=True,
        method='html',
        encoding='unicode',
    )
    with open(path, 'w') as file:
        file.write(html)

    # Now, try to run tidy on it. Only do it if tidy exists.
    # We don't want lines to wrap, since it produces invalid markdown.
    tidy = shutil.which('tidy')
    if tidy is not None:
        subprocess.run(
            [tidy, '-i', '-m', '-w', '150000', path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

def main():
    '''Process the ENEX file and extract all resources.'''

    args = parser.parse_args()
    notes_dir = os.path.join(args.output_dir, 'html_notes')
    os.makedirs(notes_dir, exist_ok=True)

    xml_parser = etree.XMLParser(huge_tree=True, strip_cdata=True)
    tree = etree.parse(args.file, parser=xml_parser)
    root = tree.getroot()
    for note in root:
        assert note.tag == 'note'
        process_note(notes_dir, note)

    basename = os.path.basename(args.file)
    tree.write(os.path.join(args.output_dir, basename))

if __name__ == '__main__':
    main()
