with source_games as (

    select *
    from {{ source('raw', 'games') }}

),

typed_games as (

    select
        game_payload:"uuid"::string                         as game_id,
        game_payload:"url"::string                          as game_url,
        to_timestamp_ntz(game_payload:"end_time"::number)   as end_time_utc,
        game_payload:"rated"::boolean                       as is_rated,
        game_payload:"time_control"::string                 as time_control,
        game_payload:"time_class"::string                   as time_class,
        game_payload:"rules"::string                        as rules,
        game_payload:"eco"::string                          as opening_url,

        game_payload:"white":"username"::string             as white_username,
        game_payload:"white":"rating"::integer              as white_rating,
        game_payload:"white":"result"::string               as white_result,
        game_payload:"accuracies":"white"::float            as white_accuracy,

        game_payload:"black":"username"::string             as black_username,
        game_payload:"black":"rating"::integer              as black_rating,
        game_payload:"black":"result"::string               as black_result,
        game_payload:"accuracies":"black"::float            as black_accuracy,

        source_file,
        loaded_at

    from source_games

)

select *
from typed_games
