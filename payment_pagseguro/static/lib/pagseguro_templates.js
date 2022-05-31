// Copyright 2022 KMEEli
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

function onChangePaymentMethod() {
    let forms = document.getElementsByClassName('form-group');
    
    if (document.getElementById("payment_form").value === "CREDIT_CARD") {
        for (let i = 1; i < forms.length; i++) {
            forms[i].style.display = 'block';
        }
    } else {
        for (let i = 1; i < forms.length; i++) {
            forms[i].style.display = 'none';
        }
    }
}

function onChangeInstallments() {
    let number = document.getElementById("installments").value;
    let table_of_factors = {
        1: 1,
        2: 0.51495,
        3: 0.3467,
        4: 0.26255,
        5: 0.2121,
        6: 0.17847,
        7: 0.15446,
        8: 0.13645,
        9: 0.12246,
        10: 0.11127,
        11: 0.10212,
        12: 0.0945,
    };
    let price_element = document.querySelector(
        "#order_total > td.text-xl-right > strong > span"
    );
    let total_price = price_element.innerHTML.replace(".", "").replace(",", ".");
    let installment_value = table_of_factors[number] * Number(total_price);
    document.getElementById("installmentsvalue").value = convert_to_currency(
        installment_value
    );
}

function convert_to_currency(value) {
    const converted = value.toLocaleString("pt-BR", {style: "currency", currency: "BRL"});
    return converted;
}
