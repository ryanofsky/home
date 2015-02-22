from gi.repository import Secret
import sys

def stuff(account, field):
  schema = Secret.Schema.new("org.mock.type.Store",
      Secret.SchemaFlags.NONE, {
          "offlineimap-account": Secret.SchemaAttributeType.STRING,
          "field": Secret.SchemaAttributeType.STRING,
       }
   )
  attributes = {
      "offlineimap-account": account,
      "field": field,
  }
  label = "offlineimap-{}-{}".format(account, field)
  return schema, attributes, label


def get_pw(account, field):
  schema, attributes, label = stuff(account, field)
  password = Secret.password_lookup_sync(schema, attributes, None)
  print "account {!r} field {!r} password {!r}".format(account, field, password)
  return password

def set_pw(account, field, password):
  schema, attributes, label = stuff(account, field)
  Secret.password_store_sync(schema, attributes, Secret.COLLECTION_DEFAULT, label, password, None)

if __name__ == "__main__":
  #print get_pw(sys.argv[1], sys.argv[2])
  password = raw_input()
  set_pw(sys.argv[1], sys.argv[2], password)
