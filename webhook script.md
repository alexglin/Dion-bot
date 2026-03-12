var params = JSON.parse(value);

if (!params.URL) {
    throw 'Parameter "URL" is required.';
}

if (!params.To) {
    throw 'Parameter "To" is required.';
}

var payload = {
    chat_id: params.To,
    subject: params.Subject || 'Zabbix alert',
    message: params.Message || '',
    severity: params.Severity || '',
    host: params.Host || '',
    event_id: params.EventID || ''
};

var req = new HttpRequest();
req.addHeader('Content-Type: application/json');

if (params.Token) {
    req.addHeader('X-Webhook-Token: ' + params.Token);
}

if (params.HTTPProxy) {
    req.setProxy(params.HTTPProxy);
}

Zabbix.log(4, '[Dion webhook] payload=' + JSON.stringify(payload));

var response = req.post(params.URL, JSON.stringify(payload));
var status = req.getStatus();

Zabbix.log(4, '[Dion webhook] status=' + status + ', response=' + response);

if (status < 200 || status >= 300) {
    throw 'HTTP error ' + status + ': ' + response;
}

return 'OK';