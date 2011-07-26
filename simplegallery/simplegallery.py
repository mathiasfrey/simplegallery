#!/usr/bin/env python2.7

import glob
import fnmatch
import os
import sys
import subprocess
import argparse
import urllib
import json
import pprint

from collections import namedtuple

Image = namedtuple('Image', ['filename', 'exif'])


#convenience functions
def is_dir(dir):
    """Custom type check for argparse"""
    if os.path.isdir(dir):
        # make sure directory has trailing '/'
        dir = '%s/' % dir.rstrip('/')
        return dir
    else:
        msg = '%s is not a valid directory' % dir
        raise argparse.ArgumentTypeError(msg)

def is_image_file(filename, extensions=['.jpg', '.jpeg', '.gif', '.png']):
    """Simple type check for directory content"""
    return any(filename.lower().endswith(e) for e in extensions)
    
def is_bad_name(filename):
    """Check if filename needs urlencoding."""
    if urllib.quote(filename) == filename: 
        return False
    return True

# main runner class
class Runner(object):
    
    def __init__(self, args):
        # save command line options
        # type, sanity and completeness lies in argparse's responsibility
        self.args = args
    
    @classmethod
    def dispatch(cls, args):
        inst = cls(args)
        inst.run()


class GalleryPrepare(Runner):
    """Read directory and create db file"""
        
    def run(self):
            
        directory = self.args.directory[0]
        self.directory = directory
        
        print 'Prepare gallery:'
        print 'Creating file *sg.json* in %s' % directory
        print 'Modify this file to exclude images, add descriptions etc.'
        
        contents = []
        
        # getting content
        bad_name = False
        for filename in glob.glob('%s*' % directory):
            if is_image_file(filename):
                if is_bad_name(filename):
                    bad_name = True
                
                try:
                    jhead = subprocess.check_output(['jhead', filename])
                except:
                    jhead = None
                
                contents.append(Image(filename=filename, exif=jhead))
                
                print '.',
        print
        if bad_name:
            print 'Warning: Some of the files contain characters that could lead to problems with your web server. Try removing whitespaces, umlauts, special characters for HTTP and other non-ASCII characters'
        
        self.contents = contents
        
        # creating db file        
        dbfile = open('%ssg.json' % directory, 'w')
        dbfile.write('#\n')
        dbdata = []
        for image in contents:
            #dbfile.write(str(image))
            data = {
                'filename': image.filename,
                'title': ''
            }
            dbdata.append(data)
        dbfile.write(json.dumps(dbdata, sort_keys=True, indent=2))
        
        
        dbfile.close()

        # archive in the end
        if self.args.archive:
            self.archive()
            
            
    def archive(self):
        """Create a tarball"""
        subprocess.call( ['tar', '-cvzf', 'sg.tgz'] + [i.filename.split('/')[-1] for i in self.contents], cwd=self.directory)


class GalleryProcess(Runner):
    """Create the gallery from sg.json file"""
    
    def run(self):
        
        directory = self.args.directory[0]
        images_per_row = 3
        
        try:
            dbfile = open('%ssg.json' % directory,'r')
        except IOError:
            print 'Could not open %ssg.json' % (directory,)
            print 'Are you sure you already ran simplegallery prepare?'
            raise SystemExit(-1)
        
        content = []
        for line in dbfile.readlines():
            # skip comments
            if not line.startswith('#'):
                content.append(line)
        dbfile.close()
        
        try:
            dbdata = json.loads(''.join(content))
        except ValueError:
            print 'sg.json is not valid json.'
            print 'Try repairing the file or generate it from scratch using prepare.'
            raise SystemExit(-1)

        print 'Creating directory _web'
        print 'I a going to store all thumbnails there' 
        subprocess.call(['mkdir', '%s_web' % directory])        
        
        # html content
        html_content= []
        # thumbnail generation
        for image in dbdata:
            
            filename = image['filename']
            tn_filename = filename.split('/')[-1]
            
            # very custom thumbnail command. there should be som flexibility
            # some day...
            subprocess.call(['convert', '-size', '500x500', filename,
                             '-thumbnail', '200x200', '-set', 'caption', '%t',
                             '-bordercolor', 'MintCream', '-background', 'black',
                             '-pointsize', '12', '-density', '96x96', '+polaroid',
                             '-resize', '70%', '-gravity', 'center',
                             '-background', 'white', '-extent', '340x340', '-trim',
                             '%(directory)s_web/%(tn_filename)s' % {
                                'directory':directory,
                                'tn_filename':tn_filename}
                             ])
            
            html_content.append('<a href="%(tn_filename)s"><img src="_web/%(tn_filename)s" /></a>' % ({'tn_filename':tn_filename}))
            print '.',
        print
    
        print 'Generating index file'
        ix = open('%sindex.html' % directory, 'w')
        
        ix.write('\n'.join(html_content))
        
        # test for archive
        if os.path.isfile("%ssg.tgz" % directory):
            # yes
            print 'I found an archive. This will be part of the gallery'
            ix.write('<a href="sg.tgz">Download archive!</a>') 
        
        ix.close()




def main():
    """Parse command line input an dispatch subcommands."""
    
    # global args
    parser = argparse.ArgumentParser(description='simplegallery: creating a simple web gallery from image directory')
    parser.add_argument('-d', '--directory', nargs=1, help='the directory you want to work with', required=True, type=is_dir)
    
    subparsers = parser.add_subparsers(help='commands')
    
    # prepare directory
    prepare_parser = subparsers.add_parser('prepare', help='Prepare directory')
    prepare_parser.add_argument('-A', '--archive', help='create a tarball?', action='store_true')
    prepare_parser.set_defaults(func=GalleryPrepare.dispatch)
    
    # process gallery
    process_parser = subparsers.add_parser('process', help='Process directory, i.e. produce the gallery')
    process_parser.set_defaults(func=GalleryProcess.dispatch)
    
    args = parser.parse_args()
    args.func(args)
    
if __name__ == '__main__':
    main()
    
    