
def cap(s):
    return s[0].upper() + s[1:]

def dump(s):
    sig = s.split(",")
    ret = sig[0]
    name = sig[1]
    args = []
    for pt, pn in zip(sig[2::2], sig[3::2]):
        args.append((pt, pn))

    atype = {"Text": "const std::string& "}
    rtype = {"Text": "std::string"}

    cliparams = ", ".join("{} {}".format(atype.get(pt, pt), pn) for pt, pn in args)
    caparams = ", ".join("{} :{}".format(pn, pt) for pt, pn in args)
    serparams = ", ".join("context.getParams().get{}()".format(cap(pn)) for pt, pn in args)

    callreq="auto request = impl->nodeClient.{name}Request();".format(name=name)
    for pt, pn in args:
        callreq += "\n        request.set{}({});".format(cap(pn), pn)
    callreq += "\n        return request;".format(cap(pn), pn)

    callret = ""
    if ret != "void":
        callret=" [&](){ return call.response->getValue(); }"

    caret = "value :{ret}".format(ret=ret) if ret != "void" else ""
    cret = rtype.get(ret, ret)

    print("""
cat >> src/ipc/client.cpp <<EOS
{cret} Node::{name}({cliparams}) const
{{
    auto call = makeCall(*impl->loop, [&]() {{
        {callreq}
    }});
    return call.send({callret} }});
}}
EOS

cat >> src/ipc/client.h <<EOS
    //! Start node.
    {cret} {name}({cliparams}) const;
EOS

cat >> src/ipc/messages.capnp <<EOS
    {name} @1 ({caparams}) -> ({caret});
EOS

cat >> src/ipc/server.cpp <<EOS
    kj::Promise<void> {name}({cname}Context context) override {{
        context.getResults().setValue({cname}({serparams}));
        return kj::READY_NOW;
    }}
EOS
""".format(name=name, cname=cap(name), ret=ret, cliparams=cliparams, caparams=caparams, serparams=serparams, callret=callret, callreq=callreq, caret=caret, cret=cret))


#dump("void,parseParameters,const std::vector<std::string>&,argv")
#dump("bool,shutdownRequested")
dump("Text,readConfigFile,Text,confPath")
dump("Text,selectParams,Text,network")
dump("void,softSetArg,Text,arg,Text,value")
dump("void,softSetBoolArg,Text,arg,bool,value")
