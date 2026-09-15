"""Invented library catalog for development retrieval checks, not production data."""


def synthetic_document():
    tables = [
        ("members", "Library member directory with contact email.", "one row per member_id"),
        ("loans", "Library book loans. Fictional fixture snapshot: 2025-01-15T12:00:00Z; not live freshness.",
         "one row per loan_id"),
        ("books", "Book catalog with titles and subject tags.", "one row per book_id"),
    ]
    columns = [
        ("members", "member_id", "Unique identifier for a library member.", "member"),
        ("members", "email", "Contact email for a library member.", None),
        ("loans", "loan_id", "Unique identifier for a book loan.", None),
        ("loans", "member_id", "Borrowing member; references members.member_id.", "member"),
        ("loans", "book_id", "Borrowed book; references books.book_id.", "book"),
        ("loans", "status", "Loan status: active or returned.", None),
        ("books", "book_id", "Unique identifier for a book.", "book"),
        ("books", "title", "Book title shown in the library catalog.", None),
        ("books", "tags", "Array of book subject tags.", None),
    ]
    objects = [
        dict(id=f"table:{name}", kind="table", name=f"library.{name}",
             source=f"library.{name}", description=description,
             grain={"description": grain}, status="published")
        for name, description, grain in tables
    ]
    objects += [
        dict(id=f"column:{table}.{name}", kind="column", name=name,
             parent_id=f"table:{table}", description=description)
        for table, name, description, _ in columns
    ]
    objects += [
        dict(id="entity:member", kind="entity", name="Member",
             description="A person registered to borrow books from the library."),
        dict(id="entity:book", kind="entity", name="Book",
             description="A cataloged publication available to borrow."),
        dict(id="join:loan-member", kind="join", name="Loan member join",
             description="Join library loans to their borrowing members.",
             left=["column:loans.member_id"], right=["column:members.member_id"],
             predicate="loans.member_id = members.member_id"),
        dict(id="relation:member-borrows-book", kind="relation", name="borrows",
             from_id="entity:member", to_id="entity:book"),
        dict(id="doctrine:active-loans", kind="doctrine", name="Count active loans",
             object_ids=["table:loans"], status="published",
             content="For currently borrowed books, count loans WHERE status = 'active'. Exclude returned loans."),
    ]
    for item in objects:
        if item["kind"] == "entity":
            item["bindings"] = [
                f"column:{table}.{name}" for table, name, _, entity in columns
                if item["id"] == f"entity:{entity}"
            ]
    return {"version": 1, "objects": objects}
