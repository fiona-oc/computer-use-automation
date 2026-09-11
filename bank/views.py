from django.shortcuts import render, redirect


MEMBERS = {
    "12345": {
        "name": "Alice Johnson",
        "checking_balance": 2500.00,
        "savings_balance": 8400.00,
    },
    "67890": {
        "name": "Bob Smith",
        "checking_balance": 1200.00,
        "savings_balance": 4300.00,
    },
}


def search_member(request):
    if request.method == "POST":
        member_id = request.POST.get("member_id")
        return redirect("member_detail", member_id=member_id)

    return render(request, "bank/search_member.html")


def member_detail(request, member_id):
    member = MEMBERS.get(member_id)

    if member is None:
        return render(
            request,
            "bank/member_not_found.html",
            {"member_id": member_id}
        )

    return render(
        request,
        "bank/member_detail.html",
        {
            "member_id": member_id,
            "member": member,
        }
    )


def open_account(request, member_id):
    member = MEMBERS.get(member_id)

    if member is None:
        return render(
            request,
            "bank/member_not_found.html",
            {"member_id": member_id}
        )

    if request.method == "POST":
        account_type = request.POST.get("account_type")

        return render(
            request,
            "bank/confirmation.html",
            {
                "member_id": member_id,
                "member": member,
                "account_type": account_type,
            }
        )

    return render(
        request,
        "bank/open_account.html",
        {
            "member_id": member_id,
            "member": member,
        }
    )
