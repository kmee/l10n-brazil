/*
Copyright (C) 2016-Today KMEE (https://kmee.com.br)
@author: Luis Felipe Mileo <mileo@kmee.com.br>
@author: Luiz Felipe do Divino <luiz.divino@kmee.com.br>
 License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
*/

odoo.define("l10n_br_pos_cfe.devices", function (require) {
    "use strict";
    var mixins = require("web.mixins");
    var ProxyDevice = require("point_of_sale.devices").ProxyDevice;
    var FiscalDocumentCFe =
        require("l10n_br_pos_cfe.FiscalDocumentCFe").FiscalDocumentCFe;

    ProxyDevice.include({
        init: function (options) {
            mixins.PropertiesMixin.init.call(this);
            var self = this;
            options = options || {};

            this.env = options.env;

            this.weighing = false;
            this.debug_weight = 0;
            this.use_debug_weight = false;

            this.paying = false;

            this.notifications = {};
            this.bypass_proxy = false;

            this.connection = null;
            this.host = "";
            this.keptalive = false;

            this.set("status", {});

            this.set_connection_status("disconnected");

            this.on("change:status", this, function (eh, status) {
                status = status.newValue;
                if (status.status === "connected" && self.printer) {
                    self.printer.print_receipt();
                }
                if (status.status === "connected" && self.fiscal_device) {
                    self.fiscal_device.send_order();
                    // TODO: Criar uma abstração na fila para processar todas as ações.
                }
            });

            this.posbox_supports_display = true;

            window.hw_proxy = this;
        },
        set_connection_status: function (status, drivers, msg = "") {
            var oldstatus = this.get("status");
            var newstatus = {};
            newstatus.status = status;
            newstatus.drivers = status === "disconnected" ? {} : oldstatus.drivers;
            newstatus.drivers = drivers ? drivers : newstatus.drivers;
            newstatus.msg = msg;
            this.set("status", newstatus);
            if (status !== "connected" && this.fiscal_device) {
                var oldstatus = this.get("status");
                if (oldstatus.drivers) {
                    if (!oldstatus.drivers.hw_fiscal) {
                        this.fiscal_device.init_job();
                    }
                }
            }
        },
        connect: function () {
            var self = this;
            this.connection = new Session(undefined, url, {use_cors: true});
            this.host = url;
            if (this.pos.config.iface_print_via_proxy) {
                this.connect_to_printer();
            }
            this.set_connection_status("connecting", {});
            this.connect_to_fiscal_device();

            return this.message("handshake").then(
                function (response) {
                    if (response) {
                        self.set_connection_status("connected");
                        localStorage.hw_proxy_url = url;
                        self.keepalive();
                    } else {
                        self.set_connection_status("disconnected");
                        console.error("Connection refused by the Proxy");
                    }
                },
                function () {
                    self.set_connection_status("disconnected");
                    console.error("Could not connect to the Proxy");
                }
            );
        },
        autoconnect: function (options) {
            var self = this;
            this.set_connection_status("connecting", {});
            if (this.pos.config.iface_print_via_proxy) {
                this.connect_to_printer();
            }
            var found_url = new Promise(function () {});

            if (options.force_ip) {
                // If the ip is forced by server config, bailout on fail
                found_url = this.try_hard_to_connect(options.force_ip, options);
            } else if (localStorage.hw_proxy_url) {
                // Try harder when we remember a good proxy url
                found_url = this.try_hard_to_connect(
                    localStorage.hw_proxy_url,
                    options
                ).catch(function () {
                    if (window.location.protocol != "https:") {
                        return self.find_proxy(options);
                    }
                });
            } else {
                // Just find something quick
                if (window.location.protocol != "https:") {
                    found_url = this.find_proxy(options);
                }
            }

            var successProm = found_url.then(function (url) {
                return self.connect(url);
            });

            successProm.catch(function () {
                self.set_connection_status("disconnected");
            });

            this.connect_to_fiscal_device();
            return successProm;
        },
        connect_to_fiscal_device: function () {
            if (this.pos.config.iface_fiscal_via_proxy) {
                this.fiscal_device = new FiscalDocumentCFe(
                    this.pos.config.proxy_ip,
                    this.pos
                );
                this.fiscal_device_contingency = this.fiscal_device;
            }
        },
    });
});
