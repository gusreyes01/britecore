function PolicyAccounting(data) {
    this.account_balance = ko.observable(data.account_balance);
}

function Policy(data) {
    this.id = ko.observable(data.id);
    this.policy_number = ko.observable(data.policy_number);
    this.effective_date = ko.observable(data.effective_date);
}

function Invoice(data) {
    this.id = ko.observable(data.id);
    this.amount_due = ko.observable(data.amount_due);
    this.due_date = ko.observable(data.due_date);
    this.bill_date = ko.observable(data.bill_date);

}

function PolicyListViewModel() {
    var self = this;
    self.policies = ko.observableArray([]);
    self.invoices = ko.observableArray([]);
    self.accounting_policies = ko.observableArray([]);
    self.newPolicyNumber = ko.observable();
    self.newPolicyDate = ko.observable();

    self.searchPolicy = function () {
        self.search();
        self.newPolicyNumber("");
        self.newPolicyDate("");
    };

    self.search = function () {
        return $.ajax({
            url: '/policies',
            contentType: 'application/json',
            type: 'POST',
            data: JSON.stringify({
                'policy_number': self.newPolicyNumber(),
                'date': self.newPolicyDate()
            }),
            success: function (policyModels) {
                if (policyModels.status !== 200) {
                    alert(policyModels.message)
                } else {
                    console.log(policyModels);
                    var p = $.map(policyModels.policies, function (item) {
                        return new Policy(item);
                    });
                    self.policies(p);

                    var i = $.map(policyModels.invoices, function (item) {
                        return new Invoice(item);
                    });
                    self.invoices(i);

                    var pa = $.map(policyModels.account_balances, function (item) {
                        return new PolicyAccounting(item);
                    });
                    self.accounting_policies(pa);


                }


                return;
            },
            error: function () {
                return console.log("Failed");
            }
        });
    };
}

ko.applyBindings(new PolicyListViewModel());