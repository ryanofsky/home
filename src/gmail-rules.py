import json
import sys
import yaml

def main():
  config = yaml.load(open(sys.argv[1]))
  Rules(config).dump()
  
  #groups = open("/home/ryanofsky/russp/groups.txt").read().split()
  #print_missing(rules, groups)

def print_missing(config, groups):
  exprs = set()
  for name, expr, tag in config["simple"]:
      exprs.add(expr)
  for group in groups:
      expr = "list:{}.google.com".format(group)
      if expr not in exprs:
          s = "    ['list/{0}', 'list:{0}.google.com',".format(group)
          print "{:80}'fuck'],".format(s)

class Rules(object):
  def __init__(self, config):
    simple = config["simple"]
    compound = config["compound"]
    self.rules = []

    for label, search, tags in simple:
      labels = [label, "tag/all"] + ["tag/" + tag for tag in tags.split() if tag]
      self.rules.append([search, labels, False])

    for label, search, move in compound:
      self.rules.append([search, [label], move])

  def dump(self):
    print "var rules = {};".format(json.dumps(self.rules, indent=4, separators=(',', ': ')))
    print GSCRIPT

# API Reference:
# 
#   https:developers.google.com/apps-script/reference/gmail/
#
GSCRIPT = """
function doGet() {
  function Engine(rules) {
    this.rules = rules;  // List [search, labels, move]
    this.labels = {};  // Map label name -> Label.
    this.cached_labels = false;  // Whether labels map is populated.
    this.skip_rules = true;  // Only create labels, skip applying rules.
  }

  Engine.prototype.getLabel = function(name) {
    if (!this.cached_labels) {
      this.cached_labels = true;
      var labels = GmailApp.getUserLabels();
      for (var i = 0; i < labels.length; ++i) {
        var label = labels[i];
        this.labels[label.getName()] = label;
      }
    }
    var label;
    if (this.labels[name]) {
      label = this.labels[name];
    } else {
      label = GmailApp.createLabel(name);
      this.labels[name] = label;
      Logger.log("Created label: " + label.getName());
    }
    return label
  }

  Engine.prototype.getNestedLabel = function(name) {
    var path = "";
    var parts = name.split("/");
    for (var i = 0; i < parts.length - 1; ++i) {
      if (i > 0) path += "/";
      path += parts[i];
      this.getLabel(path);
    }
    return this.getLabel(name);
  }

  Engine.prototype.run = function() {
    for (var i = 0; i < this.rules.length; ++i) {
      var search = this.rules[i][0];
      var label_names = this.rules[i][1];
      var archive = this.rules[i][2];

      var labels = [];
      for (var j = 0; j < label_names.length; ++j) {
        labels.push(this.getNestedLabel(label_names[j]));
      }

      var query = search + " -label:(" + label_names.join(" ") + ")";

      if (this.skip_rules) continue;
      // FIXME: Running all these mostly empty queries in sequence is too slow.
      // Fow now, splitting the input in half and running the script twice is good
      // enough, but a better approach would be to do something like (psuedocode):
      /*
      batch_queries.push(query);
      if (i % 10 == 0 || i == this.rules.length - 1) {
        var combined_query = "{ ";
        for (var j = 0; j < batch_queries.length; ++j) {
          combined_query += "(" + batch_queries[j] + ") ";
        }
        combined_query += "}";
        var combined_threads = GmailApp.search(query, 0, 1);
        if (!threads || threads.length) {
          continue;
        }
        // At this point hfound nonzero, so go back and do lookups for queries [i-10..i].
      } else {
        continue;
      }
      */

      while (true) {
        Logger.log("Search: " + query);
        var threads = GmailApp.search(query, 0, 100);
        if (!threads || !threads.length) {
          break;
        }
        for (var j = 0; j < labels.length; ++j) {
          var label = labels[j];
          Logger.log("Applying label: " + label.getName() + " to " + threads.length + " threads.");
          label.addToThreads(threads);
          if (archive) GmailApp.moveThreadsToArchive(threads);
        }
      }
    }
  }

  Engine.prototype.xml = function() {
    var id = 0;
    var date = "2014-03-16T20:16:59Z";
    var atom = XmlService.getNamespace('http://www.w3.org/2005/Atom');
    var apps = XmlService.getNamespace('apps', 'http://schemas.google.com/apps/2006');
    var feed = XmlService.createElement('feed', atom);
    feed.addContent(XmlService.createElement('title', atom).setText('Mail Filters'));
    feed.addContent(XmlService.createElement('id', atom).setText("id" + (++id)));
    feed.addContent(XmlService.createElement('updated', atom).setText(date));
    feed.addContent(XmlService.createElement('author', atom)
      .addContent(XmlService.createElement('name', atom).setText('Russell Yanofsky'))
      .addContent(XmlService.createElement('email', atom).setText('ryanofsky@google.com')));
    for (var i = 0; i < this.rules.length; ++i) {
      var search = this.rules[i][0];
      var labels = this.rules[i][1];
      var archive = this.rules[i][2];
      for (var j = 0; j < labels.length; ++j) {
        var label = labels[j];
        var entry = XmlService.createElement('entry', atom)
          .addContent(XmlService.createElement('category', atom).setAttribute('term', 'filter'))
          .addContent(XmlService.createElement('title', atom).setText('Mail Filter'))
          .addContent(XmlService.createElement('id', atom).setText("id" + (++id)))
          .addContent(XmlService.createElement('updated', atom).setText(date))
          .addContent(XmlService.createElement('content', atom))
          .addContent(XmlService.createElement('property', apps)
             .setAttribute('name', 'hasTheWord').setAttribute('value', search))
          .addContent(XmlService.createElement('property', apps)
             .setAttribute('name', 'label').setAttribute('value', label))
          .addContent(XmlService.createElement('property', apps)
             .setAttribute('name', 'shouldNeverSpam').setAttribute('value', 'true'));
        if (archive) {
          entry.addContent(XmlService.createElement('property', apps)
            .setAttribute('name', 'shouldArchive').setAttribute('value', 'true'));
        }
        feed.addContent(entry);
      }
    }
    var document = XmlService.createDocument(feed);
    var xml = XmlService.getPrettyFormat().format(document)
    return xml;
  }

  var engine = new Engine(rules);
  engine.run();
  return ContentService.createTextOutput(engine.xml());
}
"""

if __name__ == "__main__":
  main()
