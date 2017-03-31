
def cap(s):
    return s[0].upper() + s[1:]

def dump(s):
    sig = s.split(",")
    ret = sig[0]
    name = sig[1]
    args = []
    for pt, pn in zip(sig[2::2], sig[3::2]):
        args.append((pt, pn))


    cliparams = ", ".join("{} {}".format(pt, pn) for pt, pn in args)
    caparams = ", ".join("{} :{}".format(pn, pt) for pt, pn in args)
    serparams = ", ".join("context.getParams.get{}()".format(cap(pn)) for pt, pn in args)

    callreq="auto request = impl->nodeClient.{name}Request();".format(name=name)
    for pt, pn in args:
        callreq += "\n    request.set{}({});".format(cap(pn), pn)

    callret="promise.wait(impl->ioContext.waitScope);"
    if ret != "void":
        callret="auto response = {}\n    return response.getValue();".format(callret)

    caret = "value :{ret}".format(ret=ret) if ret != "void" else ""

    print("""
cat >> src/ipc/client.cpp <<EOS
{ret} Node::{name}({cliparams}) const
{{
    {callreq}
    auto promise = request.send();
    {callret}
}}
EOS

cat >> src/ipc/client.h <<EOS
    //! Start node.
    {ret} {name}({cliparams}) const;
EOS

cat >> src/ipc/messages.capnp <<EOS
    {name} @1 ({caparams}) -> (caret);
EOS

cat >> src/ipc/server.cpp <<EOS
    kj::Promise<void> {name}({cname}Context context) override {{
        context.getResults().setValue({cname}({serparams}));
        return kj::READY_NOW;
    }}
EOS
""".format(name=name, cname=cap(name), ret=ret, cliparams=cliparams, caparams=caparams, serparams=serparams, callret=callret, callreq=callreq, caret=caret))


#dump("void,parseParameters,const std::vector<std::string>&,argv")
dump("bool,shutdownRequested")
