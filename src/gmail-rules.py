import json
import sys
import yaml
import re

from xml.sax.saxutils import quoteattr

def main():
  config = yaml.load(open(sys.argv[1]))
  rules = Rules(config)
  #rules.dump_js()
  rules.dump_xml()

class Rules(object):
  def __init__(self, config):
    self.rules = config["rules"]

  def dump_js(self):
    print "var rules = {};".format(json.dumps(self.rules, indent=4, separators=(',', ': ')))

  def dump_xml(self):
    print '<?xml version="1.0" encoding="UTF-8"?>'
    print '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:apps="http://schemas.google.com/apps/2006">'
    print '  <title>Mail Filters</title>'
    print '  <id>id1</id>'
    print '  <updated>2014-03-16T20:16:59Z</updated>'
    print '  <author>'
    print '    <name>Russell Yanofsky</name>'
    print '    <email>russ@yanofsky.org</email>'
    print '  </author>'
    id = 1
    for search, labels, move in self.rules:
      for label in labels:
        id += 1
        print '  <entry>'
        print '    <category term="filter" />'
        print '    <title>Mail Filter</title>'
        print '    <id>id{}</id>'.format(id)
        print '    <updated>2014-03-16T20:16:59Z</updated>'
        print '    <content />'
        print '    <apps:property name="hasTheWord" value={} />'.format(quoteattr(search))
        print '    <apps:property name="label" value={} />'.format(quoteattr(label))
        if move:
          print '    <apps:property name="shouldNeverSpam" value="true" />'
          print '    <apps:property name="shouldArchive" value="true" />'
        print '  </entry>'
    print '</feed>'

if __name__ == "__main__":
  main()
