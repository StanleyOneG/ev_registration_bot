module default {
    type Commune {
        required property title: str {
            constraint one_of ('Север-американские', 'Северо-Германские');
        };
        required property calendar_google_id: str;
        required property creds: json;
        required property token: json;
        required property cdate: datetime {
            default := datetime_of_transaction();
        };
        required property mdate: datetime {
            default := datetime_of_transaction();
        };
    };

    type VisitType {
        required property title: str {
            constraint one_of ('Лекция', 'Терапия');
        };
        required property cdate: datetime {
            default := datetime_of_transaction();
        };
        required property mdate: datetime {
            default := datetime_of_transaction();
        };
    };

    type Event {
        required property date: datetime;
        required link commune: Commune {
            constraint exclusive;
            on source delete delete target;
        };
        required link visit_type: VisitType {
            constraint exclusive;
        };
        required property start_time: datetime;
        required property end_time: datetime;
        property total_guests: int64;
        required property event_google_id: str;
        required property cdate: datetime {
            default := datetime_of_transaction();
        };
        required property mdate: datetime {
            default := datetime_of_transaction();
        }; 
    };

    type Person {
        required property name: str;
        property phone_number: int64;
        multi link events: Event {
            constraint exclusive;
        };
        required property cdate: datetime {
            default := datetime_of_transaction();
        };
        required property mdate: datetime {
            default := datetime_of_transaction();
        }; 
    };

}
