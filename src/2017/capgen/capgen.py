
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

ptype = {
    "const std::string&": "Text",
    "bool": "Bool",
    "int": "Int32",
    "unsigned int": "UInt32",
}

def dumpc(ret, params, name):
    args = [] # (name, type)
    for param in params.split(", "):
        if not param:
            continue
        args.append(param.rsplit(" ", 1))

    sub = {
        "name": name,
        "c_args": ", ".join("{} {}".format(t, n) for t, n in args),
        "c_sig": "void({})".format(", ".join(t for t, n in args)),
        "p_sig": "({}) -> ({})".format(
            ", ".join("{} :{}".format(n, ptype[t]) for t, n in args),
            "value :{}".format(ptype[ret]) if ret != "void" else ""),
        "c_getargs": ", ".join("context.getParams().get{}()".format(cap(n)) for t, n in args),
        "c_setargs": "\n                    ".join("request.set{}({});".format(cap(n), n) for t, n in args),
        "c_setret" : "[&](){ return call.response->getValue(); }" if ret != "void" else "",
    }

    print("""
cat >> src/ipc/client.cpp <<EOS

//! Forwarder for handle{name} callback.
class {name}CallbackServer final : public messages::{name}Callback::Server
{{
public:
    {name}CallbackServer(std::function<{c_sig}> callback) : callback(std::move(callback)) {{}}
    kj::Promise<void> call(CallContext context) override
    {{
        callback({c_getargs});
        return kj::READY_NOW;
    }}

    std::function<{c_sig}> callback;
}};

std::unique_ptr<Handler> Node::handle{name}(std::function<{c_sig}> callback) const
{{
    auto call = _::MakeCall(*impl->loop, [&]() {{
        auto request = impl->nodeClient.handle{name}Request();
        request.setCallback(kj::heap<{name}CallbackServer>(std::move(callback)));
        return request;
    }});
    return call.send([&]() {{ return Factory::MakeImpl<Handler>(*impl->loop, call.response->getHandler()); }});
}}
EOS

cat >> src/ipc/client.h <<EOS
    //! Register handler for node init messages.
    std::unique_ptr<Handler> handle{name}(std::function<{c_sig}>) const;
EOS

cat >> src/ipc/messages.capnp <<EOS
    handle{name} @9 (callback: {name}Callback) -> (handler :Handler);

interface {name}Callback {{
    call @0 {p_sig};
}}
EOS

cat >> src/ipc/server.cpp <<EOS
    kj::Promise<void> handle{name}(Handle{name}Context context) override
    {{
        SetHandler(context, [this](messages::{name}Callback::Client& client) {{
            return uiInterface.{name}.connect([this, &client]({c_args}) {{
                auto call = _::MakeCall(this->loop, [&]() {{
                    auto request = client.callRequest();
                    {c_setargs}
                    return request;
                }});
                return call.send({c_setret});
            }});

        }});
        return kj::READY_NOW;
    }}
EOS
""".format(**sub))

#dump("void,parseParameters,const std::vector<std::string>&,argv")
#dump("bool,shutdownRequested")
#dump("Text,readConfigFile,Text,confPath")
#dump("Text,selectParams,Text,network")
#dump("void,softSetArg,Text,arg,Text,value")
#dump("void,softSetBoolArg,Text,arg,bool,value")
dumpc("bool", "const std::string& message, const std::string& caption, unsigned int style", "ThreadSafeMessageBox")
dumpc("bool", "const std::string& message, const std::string& noninteractive_message, const std::string& caption, int style", "ThreadSafeQuestion")
dumpc("void", "const std::string& message", "InitMessage")
dumpc("void", "int newNumConnections", "NotifyNumConnectionsChanged")
dumpc("void", "bool networkActive", "NotifyNetworkActiveChanged")
dumpc("void", "", "NotifyAlertChanged")
dumpc("void", "CWallet* wallet", "LoadWallet")
dumpc("void", "const std::string& title, int nProgress", "ShowProgress")
dumpc("void", "bool, const CBlockIndex *", "NotifyBlockTip")
dumpc("void", "bool, const CBlockIndex *", "NotifyHeaderTip")
dumpc("void", "void", "BannedListChanged")
