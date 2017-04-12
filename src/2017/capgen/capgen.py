import re

def cap(s):
    return s[0].upper() + s[1:]

def comment(s):
    return cap(re.sub("([a-z0-9])([A-Z])", r"\1 \2", s).lower())

ptype = {
    "const std::string&": "Text",
    "bool": "Bool",
    "int": "Int32",
    "int64_t": "Int64",
    "unsigned int": "UInt32",
    "double": "Float64",
    "banmap_t": "BanMap",
    "std::string": "Text",
    "size_t": "UInt64",
    "CFeeRate": "Data",
    "CAmount": "Int64",
    "const CTransaction&": "Data",
    "const uint256": "Data",
    "CCoins": "Data",
    "Network": "Int32",
    "proxyType&": "Data",
    "NodeId": "Int64",
    "const CNetAddr&": "Data",
    "const CSubNet&": "Data",
    "BanReason": "Int32",
    "UniValue": "Text",
    "std::vector<std::string>": "List(Text)",
}

def dump(ret, params, name):
    args = [] # (name, type)
    for param in params.split(", "):
        if not param:
            continue
        args.append(param.rsplit(" ", 1))

    sub = {
        "name": name,
        "cap_name": cap(name),
        "comment": comment(name),
        "c_ret": ret,
        "c_argnames": ", ".join(n for t, n in args),
        "c_args": ", ".join("{} {}".format(t, n) for t, n in args),
        "c_sig": "void({})".format(", ".join(t for t, n in args)),
        "p_sig": "({}) -> ({})".format(
            ", ".join("{} :{}".format(n, ptype[t]) for t, n in args),
            "value :{}".format(ptype[ret]) if ret != "void" else ""),
        "c_getargs": ", ".join("context.getParams().get{}()".format(cap(n)) for t, n in args),
        "c_setargs": "\n                    ".join("request.set{}({});".format(cap(n), n) for t, n in args),
        "c_getret" : "[&](){ return call.response->getValue(); }" if ret != "void" else "",
    }

    sub["c_callimpl"] = "impl->{name}({c_getargs})".format(**sub)
    if ret != "void":
      sub["c_callimpl"] = "context.getResults().setValue({c_callimpl})".format(**sub)

    print("""
cat >> src/ipc/client.cpp <<EOS
    {c_ret} {name}({c_args}) override
    {{
        auto call = util::MakeCall(loop, [&]() {{
            auto request = client.{name}Request();
            {c_setargs}
            return request;
        }});
        return call.send({c_getret});
    }}
EOS

cat >> src/ipc/interfaces.cpp <<EOS
    {c_ret} {name}({c_args}) override {{ ::{cap_name}({c_argnames}); }}
EOS

cat >> src/ipc/interfaces.h <<EOS
    //! {comment}.
    virtual {c_ret} {name}({c_args}) = 0;
EOS

cat >> src/ipc/messages.capnp <<EOS
    {name} @99 {p_sig};
EOS

cat >> src/ipc/server.cpp <<EOS
    kj::Promise<void> {name}({cap_name}Context context) override
    {{
        {c_callimpl};
        return kj::READY_NOW;
    }}
EOS
""".format(**sub))

def dumpc(ret, params, nayy):
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
        "c_getret" : "[&](){ return call.response->getValue(); }" if ret != "void" else "",
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
                return call.send({c_getret});
            }});

        }});
        return kj::READY_NOW;
    }}
EOS
""".format(**sub))

#dump("bool,getNodeStateStats,NodeId nodeid,CNodeStateStats &,stats")
#dump("void,getNodeStats,std::vector<CNodeStats>&,vstats")
#dump("void,parseParameters,const std::vector<std::string>&,argv")
#dump("bool,shutdownRequested")
#dump("Text,readConfigFile,Text,confPath")
#dump("Text,selectParams,Text,network")
#dump("void,softSetArg,Text,arg,Text,value")
#dump("void,softSetBoolArg,Text,arg,bool,value")
#dumpc("bool", "const std::string& message, const std::string& caption, unsigned int style", "ThreadSafeMessageBox")
#dumpc("bool", "const std::string& message, const std::string& noninteractive_message, const std::string& caption, int style", "ThreadSafeQuestion")
#dumpc("void", "const std::string& message", "InitMessage")
#dumpc("void", "int newNumConnections", "NotifyNumConnectionsChanged")
#dumpc("void", "bool networkActive", "NotifyNetworkActiveChanged")
#dumpc("void", "", "NotifyAlertChanged")
#dumpc("void", "const std::string& title, int nProgress", "ShowProgress")
#dumpc("void", "bool initialDownload, int height, int64_t blockTime, double verificationProgress", "NotifyBlockTip")
#dumpc("void", "bool initialDownload, int height, int64_t blockTime, double verificationProgress", "NotifyHeaderTip")
#dumpc("void", "", "BannedListChanged")
#dump("bool", "banmap_t banMap", "getBanned")
#dump("int", "unsigned int flags", "getNumConnections")
dump("std::string", "const std::string& type", "getWarnings")
dump("void", "", "initLogging")
dump("void", "", "initParameterInteraction")
dump("void", "", "startShutdown")
dump("double", "", "getVerificationProgress")
dump("int", "", "getNumBlocks") # chainActive.Height()
dump("int64_t", "", "getLastBlockTime") # chainActive.Tip()->GetBlockTime()
dump("int", "", "getHeaderTipHeight") # pindexBestHeader)->nHeight
dump("int64_t", "", "getHeaderTipTime") # pindexBestHeader)->GetBlockTime()
dump("int64_t", "", "GetTotalBytesRecv")
dump("int64_t", "", "GetTotalBytesSent")
dump("size_t", "", "getMempoolSize")
dump("size_t", "", "getMempoolDynamicUsage")
dump("double", "", "getVerificationProgress")
dump("bool", "", "IsInitialBlockDownload")
dump("bool", "", "getReindex") #fReindex
dump("bool", "", "getImporting") #fImporting
dump("void", "bool active", "setNetworkActive")
dump("bool", "", "getNetworkActive")
dump("CFeeRate", "", "getDustRelayFee")
dump("unsigned int", "", "getTxConfirmTarget")  # nTxConfirmTarget
dump("bool", "", "getWalletRbf")  # fWalletRbf
dump("CAmount", "unsigned int txBytes", "getMinimumFee")
dump("CAmount", "unsigned int txBytes", "getRequiredFee")
dump("CFeeRate", "", "estimateSmartFee")
dump("CFeeRate", "", "getPayTxFee") # payTxFee
dump("CFeeRate", "", "getMaxTxFee") # maxTxFee
dump("void", "CFeeRate rate", "setPayTxFee") # payTxFee
dump("void", "CFeeRate rate", "setPayTxFee") # payTxFee
dump("void", "const std::string& network", "setNetwork") # SelectParams
dump("std::string", "", "getNetwork") # Params()).NetworkIDString()
dump("int64_t", "const CTransaction& transaction", "getVirtualTransactionSize")
dump("bool", "const uint256 &txid, CCoins &coins", "getCoins")
dump("bool", "Network net, proxyType& proxyInfoOut", "GetProxy")
dump("void", "bool useUPnP", "mapPort")
dump("void", "NodeId id", "disconnectNode")
dump("void", "const CNetAddr& netAddr, BanReason reason, int64_t bantimeoffset", "banNode")
dump("void", "const CSubNet& ip", "unbanNode")
dump("std::string", "const std::string& method, UniValue params", "executeRpc") # tableRPC.execute(req)
dump("std::vector<std::string>", "", "listRpcCommands") # listCommands
