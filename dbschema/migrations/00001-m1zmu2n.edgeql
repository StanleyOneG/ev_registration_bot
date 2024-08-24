CREATE MIGRATION m1zmu2nm24bfr6gnlffe2nak45g2w4gtq7vnrayuixvufdpfln7wra
    ONTO initial
{
  CREATE TYPE default::Commune {
      CREATE REQUIRED PROPERTY calendar_google_id: std::str;
      CREATE REQUIRED PROPERTY cdate: std::datetime {
          SET default := (std::datetime_of_transaction());
      };
      CREATE REQUIRED PROPERTY creds: std::json;
      CREATE REQUIRED PROPERTY mdate: std::datetime {
          SET default := (std::datetime_of_transaction());
      };
      CREATE REQUIRED PROPERTY title: std::str {
          CREATE CONSTRAINT std::one_of('Север-американские', 'Северо-Германские');
      };
      CREATE REQUIRED PROPERTY token: std::json;
  };
  CREATE TYPE default::VisitType {
      CREATE REQUIRED PROPERTY cdate: std::datetime {
          SET default := (std::datetime_of_transaction());
      };
      CREATE REQUIRED PROPERTY mdate: std::datetime {
          SET default := (std::datetime_of_transaction());
      };
      CREATE REQUIRED PROPERTY title: std::str {
          CREATE CONSTRAINT std::one_of('Лекция', 'Терапия');
      };
  };
  CREATE TYPE default::Event {
      CREATE REQUIRED LINK commune: default::Commune {
          ON SOURCE DELETE DELETE TARGET;
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED LINK visit_type: default::VisitType {
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY cdate: std::datetime {
          SET default := (std::datetime_of_transaction());
      };
      CREATE REQUIRED PROPERTY date: std::datetime;
      CREATE REQUIRED PROPERTY end_time: std::datetime;
      CREATE REQUIRED PROPERTY event_google_id: std::str;
      CREATE REQUIRED PROPERTY mdate: std::datetime {
          SET default := (std::datetime_of_transaction());
      };
      CREATE REQUIRED PROPERTY start_time: std::datetime;
      CREATE PROPERTY total_guests: std::int64;
  };
  CREATE TYPE default::Person {
      CREATE MULTI LINK events: default::Event {
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY cdate: std::datetime {
          SET default := (std::datetime_of_transaction());
      };
      CREATE REQUIRED PROPERTY mdate: std::datetime {
          SET default := (std::datetime_of_transaction());
      };
      CREATE REQUIRED PROPERTY name: std::str;
      CREATE PROPERTY phone_number: std::int64;
  };
};
