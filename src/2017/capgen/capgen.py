import re
from collections import namedtuple

def cap(s):
    return s[0].upper() + s[1:]

def comment(s):
    return re.sub("([a-z0-9])([A-Z])", r"\1 \2", s).lower()

Param = namedtuple("Param", "type output")

ptype = {
    "BanReason": Param("Int32", False),
    "CAmount": Param("Int64", False),
    "CAmount&": Param("Int64", True),
    "CCoins": Param("Data", False),
    "CCoins&": Param("Data", True),
    "CConnman::NumConnections": Param("Int32", False),
    "CFeeRate": Param("Data", False),
    "CKey&": Param("Data", True),
    "CPubKey&": Param("Data", True),
    "CTransactionRef": Param("Data", False),
    "CValidationState&": Param("Text", True),
    "ChangeType": Param("Int32", False),
    "CoinsList": Param("CoinsList", False),
    "HelpMessageMode": Param("Int32", False),
    "Network": Param("Int32", False),
    "NodeId": Param("Int64", False),
    "NodesStats&": Param("NodesStats", True),
    "RPCTimerInterface*": Param(None, False),
    "UniValue": Param("Text", False),
    "WalletBalances": Param("WalletBalances", False),
    "WalletBalances&": Param("WalletBalances", True),
    "WalletOrderForm": Param("WalletOrderForm", False),
    "WalletOrderForm&": Param("WalletOrderForm", True),
    "WalletTx": Param("WalletTx", False),
    "WalletTxStatus&": Param("WalletTxStatus", True),
    "WalletValueMap": Param("WalletValueMap", False),
    "banmap_t": Param("BanMap", False),
    "banmap_t&": Param("BanMap", True),
    "bool": Param("Bool", False),
    "bool&": Param("Bool", True),
    "const CCoinControl&": Param("CoinControl", False),
    "const CCoinControl*": Param("CoinControl", False),
    "const CKeyID&": Param("Data", False),
    "const CNetAddr&": Param("Data", False),
    "const COutPoint&": Param("Data", False),
    "const CSubNet&": Param("Data", False),
    "const CTransaction&": Param("Data", False),
    "const CTxDestination&": Param("TxDestination", False),
    "const CTxIn&": Param("Data", False),
    "const CTxOut&": Param("Data", False),
    "const SecureString&": Param("Data", False),
    "const UniValue&": Param("Text", False),
    "const char* const": Param("Text", False),
    "const std::string&": Param("Text", False),
    "const std::vector<COutPoint>&": Param("List(Data)", False),
    "const std::vector<CRecipient>&": Param("List(Recipient)", False),
    "const uint256": Param("Data", False),
    "const uint256&": Param("Data", False),
    "double": Param("Float64", False),
    "int": Param("Int32", False),
    "int&": Param("Int32", True),
    "int*": Param("Int32", True),
    "int64_t": Param("Int64", False),
    "int64_t&": Param("Int64", True),
    "isminefilter": Param("Int32", False),
    "isminetype": Param("Int32", False),
    "isminetype*": Param("Int32", True),
    "proxyType&": Param("Data", True),
    "size_t": Param("UInt64", False),
    "std::set<CTxDestination>": Param("List(TxDestination)", False),
    "std::string": Param("Text", False),
    "std::string&": Param("Text", True),
    "std::string*": Param("Text", True),
    "std::unique_ptr<PendingWalletTx>": Param("PendingWalletTx", False),
    "std::unique_ptr<Wallet>": Param("Wallet", False),
    "std::vector<COutPoint>&": Param("List(Data)", True),
    "std::vector<WalletAddress>": Param("List(WalletAddress)", False),
    "std::vector<WalletTx>": Param("List(WalletTx)", False),
    "std::vector<WalletTxOut>": Param("List(WalletTxOut)", False),
    "std::vector<std::string>": Param("List(Text)", False),
    "std::vector<std::string>&": Param("List(Text)", True),
    "uint32_t": Param("UInt32", False),
    "unsigned int": Param("UInt32", False),
}

def dump(classname, template, ret, name, params=""):
    args = [] # (name, type)
    for param in params.split(", "):
        if not param:
            continue
        args.append(param.rsplit(" ", 1))


    c_setargs = ["request.set{}({});".format(cap(n), n) for t, n in args if not ptype[t].output]

    sub = {
        "classname": classname,
        "name": name,
        "cap_name": cap(name),
        "comment": comment(name),
        "comment_cap": cap(comment(name)),
        "c_ret": ret,
        "c_argnames": ", ".join(n for t, n in args),
        "c_args": ", ".join("{} {}".format(t, n) for t, n in args),
        "c_sig": "{}({})".format(ret, ", ".join("{} {}".format(t, n) for t, n in args)),
        "p_sig": "({}) -> ({})".format(
            ", ".join("{} :{}".format(n, ptype[t].type) for t, n in args if not ptype[t].output),
            ", ".join(
                ["{} :{}".format(n, ptype[t].type) for t, n in args if ptype[t].output] +
                (["value :{}".format(ptype[ret].type)] if ret != "void" else []))),
        "c_getargs": ", ".join("context.getParams().get{}()".format(cap(n)) if not ptype[t].output else n for t, n in args),
        "c_setargs": "\n            ".join(c_setargs),
        "c_setargs_d": "\n                    ".join(c_setargs),
    }

    c_callimpl = []
    for t, n in args:
        if ptype[t].output:
            c_callimpl.append("{} {};".format(t, n))
    call = "impl->{name}({c_getargs})".format(**sub)
    if ret != "void":
        c_callimpl.append("context.getResults().setValue({});".format(call))
    else:
        c_callimpl.append("{};".format(call))
    for t, n in args:
        if ptype[t].output:
            c_callimpl.append("context.getResults().set{}({});".format(cap(n), n))

    c_getret = []

    for t, n in args:
        if ptype[t].output:
            c_getret.append("{} = call.response->get{}();".format(n, cap(n)))
    if ret != "void":
        c_getret.append("return call.response->getValue();")

    sub.update({
        "c_getret" : "[&](){{ {} }}".format(" ".join(c_getret)) if c_getret else "",
        "c_callimpl": "\n        ".join(c_callimpl),
    })


    print(template.format(**sub))

CALL_TEMPLATE = """
cat >> src/ipc/capnp/interfaces.cpp <<EOS
    {c_ret} {name}({c_args}) override
    {{
        auto call = MakeCall(loop, [&]() {{
            auto request = client.{name}Request();
            {c_setargs}
            return request;
        }});
        return call.send({c_getret});
    }}
EOS

cat >> src/ipc/local/interfaces.cpp_ <<EOS
    {c_ret} {name}({c_args}) override {{ ::{cap_name}({c_argnames}); }}
EOS

cat >> src/ipc/interfaces.h_ <<EOS
    //! {comment_cap}.
    virtual {c_ret} {name}({c_args}) = 0;
EOS

cat >> src/ipc/capnp/messages.capnp <<EOS
    {name} @99 {p_sig};
EOS

cat >> src/ipc/capnp/server.cpp <<EOS
    kj::Promise<void> {name}({cap_name}Context context) override
    {{
        {c_callimpl}
        return kj::READY_NOW;
    }}
EOS
"""

CALLBACK_TEMPLATE = """
cat >> src/ipc/capnp/interfaces.cpp <<EOS

class {name}CallbackServer final : public messages::{name}Callback::Server
{{
public:
    {name}CallbackServer({classname}::{name}Fn fn) : fn(std::move(fn)) {{}}

    kj::Promise<void> call(CallContext context) override
    {{
        fn({c_getargs});
        return kj::READY_NOW;
    }}

    {classname}::{name}Fn fn;
}};

    std::unique_ptr<Handler> handle{name}({name}Fn fn) override
    {{
        auto call = MakeCall(loop, [&]() {{
            auto request = client.handle{name}Request();
            request.setCallback(kj::heap<{name}CallbackServer>(std::move(fn)));
            return request;
        }});
        return call.send([&]() {{ return MakeUnique<HandlerImpl>(loop, call.response->getHandler()); }});
    }}
EOS

cat >> src/ipc/interfaces.h_ <<EOS
    //! Register handler for {comment} messages.
    using {name}Fn = std::function<{c_sig}>;
    virtual std::unique_ptr<Handler> handle{name}({name}Fn fn) = 0;
EOS

cat >> src/ipc/local/interfaces.cpp <<EOS
    std::unique_ptr<Handler> handle{name}({name}Fn fn) override
    {{
        return MakeUnique<HandlerImpl>(uiInterface.{name}.connect(fn));
    }}
EOS

cat >> src/ipc/capnp/messages.capnp <<EOS
    handle{name} @9 (callback: {name}Callback) -> (handler :Handler);

interface {name}Callback {{
    call @0 {p_sig};
}}
EOS

cat >> src/ipc/capnp/server.cpp <<EOS
    kj::Promise<void> handle{name}(Handle{name}Context context) override
    {{
        SetHandler(context, [this](messages::{name}Callback::Client& client) {{
            return impl->handle{name}([this, &client]({c_args}) {{
                auto call = MakeCall(this->loop, [&]() {{
                    auto request = client.callRequest();
                    {c_setargs_d}
                    return request;
                }});
                return call.send({c_getret});
            }});

        }});
        return kj::READY_NOW;
    }}
EOS
"""






dump("Node", CALL_TEMPLATE, "void", "parseParameters", "int argc, const char* const argv")
dump("Node", CALL_TEMPLATE, "bool", "softSetArg", "const std::string& arg, const std::string& value")
dump("Node", CALL_TEMPLATE, "bool", "softSetBoolArg", "const std::string& arg, bool value")
dump("Node", CALL_TEMPLATE, "void", "readConfigFile", "const std::string& confPath")
dump("Node", CALL_TEMPLATE, "void", "selectParams", "const std::string& network")
dump("Node", CALL_TEMPLATE, "std::string", "getNetwork")
dump("Node", CALL_TEMPLATE, "void", "initLogging")
dump("Node", CALL_TEMPLATE, "void", "initParameterInteraction")
dump("Node", CALL_TEMPLATE, "std::string", "getWarnings", "const std::string& type")
dump("Node", CALL_TEMPLATE, "uint32_t", "getLogCategories")
dump("Node", CALL_TEMPLATE, "bool", "appInit")
dump("Node", CALL_TEMPLATE, "void", "appShutdown")
dump("Node", CALL_TEMPLATE, "void", "startShutdown")
dump("Node", CALL_TEMPLATE, "bool", "shutdownRequested")
dump("Node", CALL_TEMPLATE, "std::string", "helpMessage", "HelpMessageMode mode")
dump("Node", CALL_TEMPLATE, "void", "mapPort", "bool useUPnP")
dump("Node", CALL_TEMPLATE, "bool", "getProxy", "Network net, proxyType& proxyInfo")
dump("Node", CALL_TEMPLATE, "size_t", "getNodeCount", "CConnman::NumConnections flags")
dump("Node", CALL_TEMPLATE, "bool", "getNodesStats", "NodesStats& stats")
dump("Node", CALL_TEMPLATE, "bool", "getBanned", "banmap_t& banMap")
dump("Node", CALL_TEMPLATE, "bool", "ban", "const CNetAddr& netAddr, BanReason reason, int64_t bantimeoffset")
dump("Node", CALL_TEMPLATE, "bool", "unban", "const CSubNet& ip")
dump("Node", CALL_TEMPLATE, "bool", "disconnect", "NodeId id")
dump("Node", CALL_TEMPLATE, "int", "getNumBlocks")
dump("Node", CALL_TEMPLATE, "int", "getHeaderTipHeight")
dump("Node", CALL_TEMPLATE, "int64_t", "getHeaderTipTime")
dump("Node", CALL_TEMPLATE, "int64_t", "getTotalBytesRecv")
dump("Node", CALL_TEMPLATE, "int64_t", "getTotalBytesSent")
dump("Node", CALL_TEMPLATE, "int64_t", "getLastBlockTime")
dump("Node", CALL_TEMPLATE, "size_t", "getMempoolSize")
dump("Node", CALL_TEMPLATE, "size_t", "getMempoolDynamicUsage")
dump("Node", CALL_TEMPLATE, "double", "getVerificationProgress")
dump("Node", CALL_TEMPLATE, "bool", "isInitialBlockDownload")
dump("Node", CALL_TEMPLATE, "bool", "getReindex")
dump("Node", CALL_TEMPLATE, "bool", "getImporting")
dump("Node", CALL_TEMPLATE, "void", "setNetworkActive", "bool active")
dump("Node", CALL_TEMPLATE, "bool", "getNetworkActive")
dump("Node", CALL_TEMPLATE, "unsigned int", "getTxConfirmTarget")
dump("Node", CALL_TEMPLATE, "bool", "getWalletRbf")
dump("Node", CALL_TEMPLATE, "CAmount", "getRequiredFee", "unsigned int txBytes")
dump("Node", CALL_TEMPLATE, "CAmount", "getMinimumFee", "unsigned int txBytes")
dump("Node", CALL_TEMPLATE, "CAmount", "getMaxTxFee")
dump("Node", CALL_TEMPLATE, "CFeeRate", "estimateSmartFee", "int nBlocks, int* answerFoundAtBlocks")
dump("Node", CALL_TEMPLATE, "CFeeRate", "getDustRelayFee")
dump("Node", CALL_TEMPLATE, "CFeeRate", "getFallbackFee")
dump("Node", CALL_TEMPLATE, "CFeeRate", "getPayTxFee")
dump("Node", CALL_TEMPLATE, "void", "setPayTxFee", "CFeeRate rate")
dump("Node", CALL_TEMPLATE, "UniValue", "executeRpc", "const std::string& command, const UniValue& params")
dump("Node", CALL_TEMPLATE, "std::vector<std::string>", "listRpcCommands")
dump("Node", CALL_TEMPLATE, "void", "rpcSetTimerInterfaceIfUnset", "RPCTimerInterface* iface")
dump("Node", CALL_TEMPLATE, "void", "rpcUnsetTimerInterface", "RPCTimerInterface* iface")
dump("Node", CALL_TEMPLATE, "bool", "getUnspentOutputs", "const uint256& txHash, CCoins& coins")
dump("Node", CALL_TEMPLATE, "std::unique_ptr<Wallet>", "getWallet")
dump("Wallet", CALL_TEMPLATE, "bool", "encryptWallet", "const SecureString& walletPassphrase")
dump("Wallet", CALL_TEMPLATE, "bool", "isCrypted")
dump("Wallet", CALL_TEMPLATE, "bool", "lock")
dump("Wallet", CALL_TEMPLATE, "bool", "unlock", "const SecureString& walletPassphrase")
dump("Wallet", CALL_TEMPLATE, "bool", "isLocked")
dump("Wallet", CALL_TEMPLATE, "bool", "changeWalletPassphrase", "const SecureString& oldWalletPassphrase, const SecureString& newWalletPassphrase")
dump("Wallet", CALL_TEMPLATE, "bool", "backupWallet", "const std::string& filename")
dump("Wallet", CALL_TEMPLATE, "bool", "getKeyFromPool", "CPubKey& result, bool internal")
dump("Wallet", CALL_TEMPLATE, "bool", "getPubKey", "const CKeyID& address, CPubKey& pubKey")
dump("Wallet", CALL_TEMPLATE, "bool", "getKey", "const CKeyID& address, CKey& key")
dump("Wallet", CALL_TEMPLATE, "bool", "haveKey", "const CKeyID& address")
dump("Wallet", CALL_TEMPLATE, "bool", "haveWatchOnly")
dump("Wallet", CALL_TEMPLATE, "bool", "setAddressBook", "const CTxDestination& dest, const std::string& name, const std::string& purpose")
dump("Wallet", CALL_TEMPLATE, "bool", "delAddressBook", "const CTxDestination& dest")
dump("Wallet", CALL_TEMPLATE, "bool", "getAddress", "const CTxDestination& dest, std::string* name, isminetype* ismine")
dump("Wallet", CALL_TEMPLATE, "std::vector<WalletAddress>", "getAddresses")
dump("Wallet", CALL_TEMPLATE, "std::set<CTxDestination>", "getAccountAddresses", "const std::string& account")
dump("Wallet", CALL_TEMPLATE, "bool", "addDestData", "const CTxDestination& dest, const std::string& key, const std::string& value")
dump("Wallet", CALL_TEMPLATE, "bool", "eraseDestData", "const CTxDestination& dest, const std::string& key")
dump("Wallet", CALL_TEMPLATE, "void", "getDestValues", "const std::string& prefix, std::vector<std::string>& values")
dump("Wallet", CALL_TEMPLATE, "void", "lockCoin", "const COutPoint& output")
dump("Wallet", CALL_TEMPLATE, "void", "unlockCoin", "const COutPoint& output")
dump("Wallet", CALL_TEMPLATE, "bool", "isLockedCoin", "const COutPoint& output")
dump("Wallet", CALL_TEMPLATE, "void", "listLockedCoins", "std::vector<COutPoint>& outputs")
dump("Wallet", CALL_TEMPLATE, "std::unique_ptr<PendingWalletTx>", "createTransaction", "const std::vector<CRecipient>& recipients, const CCoinControl* coinControl, bool sign, int& changePos, CAmount& fee, std::string& failReason")
dump("Wallet", CALL_TEMPLATE, "bool", "transactionCanBeAbandoned", "const uint256& txHash")
dump("Wallet", CALL_TEMPLATE, "bool", "abandonTransaction", "const uint256& txHash")
dump("Wallet", CALL_TEMPLATE, "CTransactionRef", "getTx", "const uint256& txHash")
dump("Wallet", CALL_TEMPLATE, "WalletTx", "getWalletTx", "const uint256& txHash")
dump("Wallet", CALL_TEMPLATE, "std::vector<WalletTx>", "getWalletTxs")
dump("Wallet", CALL_TEMPLATE, "bool", "tryGetTxStatus", "const uint256& txHash, WalletTxStatus& txStatus, int& numBlocks, int64_t& adjustedTime")
dump("Wallet", CALL_TEMPLATE, "WalletTx", "getWalletTxDetails", "const uint256& txHash, WalletTxStatus& txStatus, WalletOrderForm& orderForm, bool& inMempool, int& numBlocks, int64_t& adjustedTime")
dump("Wallet", CALL_TEMPLATE, "WalletBalances", "getBalances")
dump("Wallet", CALL_TEMPLATE, "bool", "tryGetBalances", "WalletBalances& balances, int& numBlocks")
dump("Wallet", CALL_TEMPLATE, "CAmount", "getBalance")
dump("Wallet", CALL_TEMPLATE, "CAmount", "getUnconfirmedBalance")
dump("Wallet", CALL_TEMPLATE, "CAmount", "getImmatureBalance")
dump("Wallet", CALL_TEMPLATE, "CAmount", "getWatchOnlyBalance")
dump("Wallet", CALL_TEMPLATE, "CAmount", "getUnconfirmedWatchOnlyBalance")
dump("Wallet", CALL_TEMPLATE, "CAmount", "getImmatureWatchOnlyBalance")
dump("Wallet", CALL_TEMPLATE, "CAmount", "getAvailableBalance", "const CCoinControl& coinControl")
dump("Wallet", CALL_TEMPLATE, "isminetype", "isMine", "const CTxIn& txin")
dump("Wallet", CALL_TEMPLATE, "isminetype", "isMine", "const CTxOut& txout")
dump("Wallet", CALL_TEMPLATE, "CAmount", "getDebit", "const CTxIn& txin, isminefilter filter")
dump("Wallet", CALL_TEMPLATE, "CAmount", "getCredit", "const CTxOut& txout, isminefilter filter")
dump("Wallet", CALL_TEMPLATE, "CoinsList", "listCoins")
dump("Wallet", CALL_TEMPLATE, "std::vector<WalletTxOut>", "getCoins", "const std::vector<COutPoint>& outputs")
dump("Wallet", CALL_TEMPLATE, "bool", "hdEnabled")
dump("WalletPendingTx", CALL_TEMPLATE, "const CTransaction&", "get")
dump("WalletPendingTx", CALL_TEMPLATE, "int64_t", "getVirtualSize")
dump("WalletPendingTx", CALL_TEMPLATE, "bool", "commit", "WalletValueMap mapValue, WalletOrderForm orderForm, std::string fromAccount, CValidationState& state")
dump("Node", CALLBACK_TEMPLATE, "void", "InitMessage", "const std::string& message")
dump("Node", CALLBACK_TEMPLATE, "bool", "MessageBox", "const std::string& message, const std::string& caption, unsigned int style")
dump("Node", CALLBACK_TEMPLATE, "bool", "Question", "const std::string& message, const std::string& nonInteractiveMessage, const std::string& caption, unsigned int style")
dump("Node", CALLBACK_TEMPLATE, "void", "ShowProgress", "const std::string& title, int progress")
dump("Node", CALLBACK_TEMPLATE, "void", "LoadWallet", "std::unique_ptr<Wallet> wallet")
dump("Node", CALLBACK_TEMPLATE, "void", "NotifyNumConnectionsChanged", "int newNumConnections")
dump("Node", CALLBACK_TEMPLATE, "void", "NotifyNetworkActiveChanged", "bool networkActive")
dump("Node", CALLBACK_TEMPLATE, "void", "NotifyAlertChanged")
dump("Node", CALLBACK_TEMPLATE, "void", "BannedListChanged")
dump("Node", CALLBACK_TEMPLATE, "void", "NotifyBlockTip", "bool initialDownload, int height, int64_t blockTime, double verificationProgress")
dump("Node", CALLBACK_TEMPLATE, "void", "NotifyHeaderTip", "bool initialDownload, int height, int64_t blockTime, double verificationProgress")
dump("Wallet", CALLBACK_TEMPLATE, "void", "ShowProgress", "const std::string& title, int progress")
dump("Wallet", CALLBACK_TEMPLATE, "void", "StatusChanged")
dump("Wallet", CALLBACK_TEMPLATE, "void", "AddressBookChanged", "const CTxDestination& address, const std::string& label, bool isMine, const std::string& purpose, ChangeType status")
dump("Wallet", CALLBACK_TEMPLATE, "void", "TransactionChanged", "const uint256& hashTx, ChangeType status, bool isCoinBase, bool isInMainChain")
dump("Wallet", CALLBACK_TEMPLATE, "void", "WatchonlyChanged", "bool haveWatchOnly")
