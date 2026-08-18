from __future__ import annotations


from omni.google_audit import (
    google_audit,
)

from omni.google_oauth import (
    google_oauth,
)


PERSON_FIELDS = (
    "names,emailAddresses,"
    "phoneNumbers,organizations"
)


class GoogleContactsService:

    def service(
        self,
    ):

        return google_oauth.service(
            "people",
            "v1",
        )


    @staticmethod
    def _person(
        person,
    ):

        names = person.get(
            "names",
            ()
        )


        emails = person.get(
            "emailAddresses",
            ()
        )


        phones = person.get(
            "phoneNumbers",
            ()
        )


        organizations = person.get(
            "organizations",
            ()
        )


        return {
            "resource_name":
                person.get(
                    "resourceName"
                ),

            "name":
                (
                    names[
                        0
                    ].get(
                        "displayName"
                    )
                    if names
                    else None
                ),

            "emails":
                tuple(
                    item.get(
                        "value"
                    )

                    for item
                    in emails

                    if item.get(
                        "value"
                    )
                ),

            "phones":
                tuple(
                    item.get(
                        "value"
                    )

                    for item
                    in phones

                    if item.get(
                        "value"
                    )
                ),

            "organizations":
                tuple(
                    {
                        "name":
                            item.get(
                                "name"
                            ),

                        "title":
                            item.get(
                                "title"
                            ),
                    }

                    for item
                    in organizations
                ),
        }


    def list(
        self,
        max_results=100,
    ):

        response = (
            self.service()
            .people()
            .connections()
            .list(
                resourceName=
                    "people/me",

                pageSize=
                    max(
                        1,
                        min(
                            int(
                                max_results
                            ),
                            1000,
                        ),
                    ),

                personFields=
                    PERSON_FIELDS,
            )
            .execute()
        )


        contacts = tuple(
            self._person(
                person
            )

            for person
            in response.get(
                "connections",
                ()
            )
        )


        google_audit.record(
            "contacts.list",
            success=True,
            metadata={
                "results":
                    len(
                        contacts
                    )
            },
        )


        return {
            "success":
                True,

            "contacts":
                contacts,
        }


    def search(
        self,
        query,
        max_results=20,
    ):

        query = str(
            query
        ).strip()


        if not query:

            return self.list(
                max_results=
                    max_results
            )


        service = self.service()


        # People API documentation recommends
        # warming the search cache first.
        try:

            (
                service.people()
                .searchContacts(
                    query="",
                    readMask=
                        PERSON_FIELDS,
                    pageSize=1,
                )
                .execute()
            )

        except Exception:

            pass


        response = (
            service.people()
            .searchContacts(
                query=
                    query,

                readMask=
                    PERSON_FIELDS,

                pageSize=
                    max(
                        1,
                        min(
                            int(
                                max_results
                            ),
                            30,
                        ),
                    ),
            )
            .execute()
        )


        contacts = []


        for result in response.get(
            "results",
            ()
        ):

            person = result.get(
                "person",
                {}
            )


            contacts.append(
                self._person(
                    person
                )
            )


        google_audit.record(
            "contacts.search",
            success=True,
            metadata={
                "query":
                    query[:300],

                "results":
                    len(
                        contacts
                    ),
            },
        )


        return {
            "success":
                True,

            "contacts":
                tuple(
                    contacts
                ),
        }


google_contacts_service = (
    GoogleContactsService()
)
