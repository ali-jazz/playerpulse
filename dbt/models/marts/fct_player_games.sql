with games as (

    select *
    from {{ ref('stg_games') }}

),

player_perspective as (

    select
        game_id,
        game_url,
        end_time_utc,
        end_time_utc::date as game_date,
        time_class,
        time_control,
        opening_url,
        is_rated,

        case
            when lower(white_username) = 'ajaza' then 'white'
            else 'black'
        end as player_color,

        case
            when lower(white_username) = 'ajaza' then white_username
            else black_username
        end as player_username,

        case
            when lower(white_username) = 'ajaza' then black_username
            else white_username
        end as opponent_username,

        case
            when lower(white_username) = 'ajaza' then white_rating
            else black_rating
        end as player_rating,

        case
            when lower(white_username) = 'ajaza' then black_rating
            else white_rating
        end as opponent_rating,

        case
            when lower(white_username) = 'ajaza' then white_result
            else black_result
        end as player_result,

        case
            when lower(white_username) = 'ajaza' then black_result
            else white_result
        end as opponent_result,

        case
            when lower(white_username) = 'ajaza' then white_accuracy
            else black_accuracy
        end as player_accuracy,

        case
            when lower(white_username) = 'ajaza' then black_accuracy
            else white_accuracy
        end as opponent_accuracy,

        source_file,
        loaded_at

    from games

    where
        lower(white_username) = 'ajaza'
        or lower(black_username) = 'ajaza'

),

final as (

    select
        *,

        case
            when player_result = 'win' then 'win'
            when opponent_result = 'win' then 'loss'
            else 'draw'
        end as game_outcome,

        player_rating - opponent_rating as rating_difference

    from player_perspective

)

select *
from final
