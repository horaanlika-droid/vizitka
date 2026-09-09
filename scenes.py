# -*- coding: utf-8 -*-
"""Сцены игры (код владельца, без изменений логики).

Фото хранятся как Telegram file_id:
- боты отправляют их напрямую через sendPhoto(file_id);
- веб-витрина показывает их через медиа-прокси /api/media/<file_id>
  (см. web/server.py), поэтому менять ничего не нужно.
"""

scenes = {
    # ========== ПРОЛОГ ==========
    "prolog_scene1": {
        "photo": "AgACAgIAAxkBAAIEYGoo04CnDSS6_BH4RN9JdJhKiHBBAALKGGsbDCFISTwPNn7AnU2lAQADAgADeQADOwQ",
        "text": "🎭 ПРОЛОГ: ПУСТОТА 🎭\n\nТы сидишь в пустой квартире. На часах три ночи. За окном тоскливая действительность, такая же пустая, как твоя жалкая жизнь. Ни работы. Ни денег. Ни друзей. Ты даже не помнишь, когда в последний раз кто-то написал тебе первым.\n\nНа столе — пустые бутылки, грязная посуда. Ты смотришь в потолок и чувствуешь, как что-то гниёт внутри.\n\n— Я никчёмный... — шепчешь ты в пустоту. Голос звучит правдиво.\n\nТелефон тускло светит. Ты листаешь телегу. Натыкаешься на странные каналы. Что-то щёлкает внутри.\n\nТы жмёшь «Подписаться»🦴",
        "choices": [
            {"text": "😖 Поскулить от страха", "next_scene": "prolog_scene2", "effects": {}}
        ]
    },
    "prolog_scene2": {
        "photo": "AgACAgIAAxkBAAIEYmoo1GQaXp1hpdEe7fXvrVY6HZNVAALOGGsbDCFISVpviG5C65fJAQADAgADeQADOwQ",
        "text": "🎭 ПРОЛОГ: ДНО 🎭\n\nЛента в чате ломится от объявлений домин.\n\n💬 «Ты ничего не стоишь. Твоё мнение — говно 💩. Твои желания — смех. Но если ты готов ползать и лизать — может, я найду тебе место у своих ног».\n\nУ тебя трясутся руки 🤯. Ты хочешь закрыть приложение. Выбросить телефон. Забыть.\n\nНо не можешь.\n\nПотому что это правда. Ты — ничтожество. И только кто-то сильнее может наполнить тебя смыслом. Даже если этот смысл — унижение 😔\n\nТы встаёшь. Надеваешь старую куртку. Выходишь под дождь.\n\nТы идёшь на встречу с той, кто относится к тебе как к жалкой шавке.\n\n🐕 Ты уже не человек. Ты вещь, которая ищет хозяина.\n\n⬇️ ГЛАВА 1 ⬇️",
        "choices": [
            {"text": "🐕 Опустить голову и идти", "next_scene": "chap1_scene1", "effects": {}}
        ]
    },

    # ========== ГЛАВА 1 ==========
    "chap1_scene1": {
        "photo": "AgACAgIAAxkBAAIEZGoo1n7EJBXLv4g7s7IdVXq034LmAALSGGsbDCFISZmXAgWb1d9KAQADAgADeQADOwQ",
        "text": "📍 ГЛАВА 1: ПОРОГ 📍\n\nТы заходишь в комнату. Пахнет пылью и дорогими духами 👠. Богиня Мила сидит на стуле, болтая ногой в гольфах, листает телефон 📱. Свет лампы падает на её лицо, оставляя половину в тени.\n\nОна даже не поднимает взгляд.\n\n— Ну что, мусор, приполз? Я ждала.\n\nТы молчишь. Сглатываешь.\n\n— Я спрашиваю, готов к дрессировке?!🐾",
        "choices": [
            {"text": "😖 Да, Богиня.. Я мусор. Поскулить", "next_scene": "chap1_scene2_good", "effects": {}},
            {"text": "😤 Я не мусор! Сжать кулаки", "next_scene": "chap1_scene2_neutral", "effects": {}},
            {"text": "😨 Опустить взгляд. Молчать. Дрожать", "next_scene": "chap1_scene2_shy", "effects": {}}
        ]
    },
    "chap1_scene2_good": {
        "photo": "AgACAgIAAxkBAAIEZmoo14gBwZA8VtK77rxLzWoQXZPGAALUGGsbDCFISce5eL9lDwWrAQADAgADeQADOwQ",
        "text": "Мила наконец поднимает глаза. Медленно. Как будто делает тебе одолжение.\n\n— Умничка, сучка. Хотя бы понимаешь, кто ты. Может, из тебя что-то выйдет. 😏\n\nОна снова утыкается в телефон. Ты стоишь на месте, боясь дышать.",
        "choices": [
            {"text": "😖 Поскулить от облегчения", "next_scene": "chap1_scene3", "effects": {}},
            {"text": "😤 Отказаться. Сказать 'нет'", "next_scene": "chap1_refuse", "effects": {}}
        ]
    },
    "chap1_scene2_neutral": {
        "photo": "AgACAgIAAxkBAAIEaGoo2APhuduwpSCdiNLQtW4tBckSAALVGGsbDCFISRueI24qAad_AQADAgADeQADOwQ",
        "text": "Богиня Мила закатывает глаза 🙄. Кладет телефон на стол.\n\n— Не мусор? А кто? Герой? Посмотри на себя. Тебя даже жалко пиздить.\n\nТы чувствуешь, как земля уходит из-под ног.",
        "choices": [
            {"text": "😞 Опустить голову. Сдаться", "next_scene": "chap1_scene3", "effects": {}},
            {"text": "😤 Отказаться. Уйти", "next_scene": "chap1_refuse", "effects": {}}
        ]
    },
    "chap1_scene2_shy": {
        "photo": "AgACAgIAAxkBAAIEamoo2GU_Xc4E2bkB8kqm5XRciW9mAALWGGsbDCFISVjZW_tyMxgcAQADAgADeQADOwQ",
        "text": "Богиня Мила хмурится 😠. Её голос становится холодным.\n\n— Молчишь? Ну и иди нахуй. Такая псина мне не нужна👋\n\nОна машет рукой в сторону двери. Ты чувствуешь, как внутри всё обрывается.",
        "choices": [
            {"text": "😖 Упасть на колени. Поскулить", "next_scene": "chap1_scene3", "effects": {}},
            {"text": "😤 Уйти молча", "next_scene": "chap1_refuse", "effects": {}}
        ]
    },
    "chap1_refuse": {
        "photo": None,
        "text": "Ты разворачиваешься и уходишь. Богиня Мила даже не смотрит вслед.\n\n— Слабак. Так и знала.\n\nТы выходишь на улицу. Пустота внутри становится ещё больше.\n\n🏁 ПЛОХАЯ КОНЦОВКА: ТРУС\n\n/reset — начать заново",
        "choices": [],
        "set_ending": "bad_early"
    },
    "chap1_scene3": {
        "photo": "AgACAgIAAxkBAAIEbGoo2lOAC8TQYlOtIb_FUujMGIzZAALZGGsbDCFISZ7G7QAB4m3b1gEAAwIAA3kAAzsE",
        "text": "Богиня Мила встаёт. Медленно подходит. Ты чувствуешь её тень, запах духов. Она смотрит сверху вниз, как на насекомое.\n\n— На колени, мразь. Жди. Пока не скажу — не поднимайся.\n\nОна наклоняется, плюёт на пол рядом с твоим лицом 💧.\n\n— Вылизывай и думай о том, кто ты есть на самом деле.\n\nВозвращается на место, утыкается в телефон. Тишина. Только тикают часы на стене ⏰\n\nТы стоишь на коленях. Твоя спина болит. Ты смотришь на её плевок.",
        "choices": [
            {"text": "🧎 Смотреть в пол. Терпеть", "next_scene": "chap1_end", "effects": {}},
            {"text": "😖 Поскулить тихонько", "next_scene": "chap1_end", "effects": {}},
            {"text": "😤 Встать и уйти", "next_scene": "chap1_refuse", "effects": {}}
        ]
    },
    "chap1_end": {
        "photo": "AgACAgIAAxkBAAIEbmoo231208aJfj7c1B_wmnhWZ98gAALaGGsbDCFISSXPl57BgjfWAQADAgADeQADOwQ",
        "text": "Проходит пять минут. Или два часа? Ты потерял счёт 😵\n\nБогиня Мила поднимает взгляд от телефона. Смотрит на тебя.\n\n— Подползи. Рядом с ногой. Учись знать место.\n\nТы ползёшь. Медленно. Глаза в пол. Она не смотрит. Листает ленту.\n\nТы замираешь у её ног. Чувствуешь тепло её тела.\n\n— Сиди. И не вздумай двигаться.\n\n🏁 КОНЕЦ ГЛАВЫ 1. Ты ещё ничего не доказал. Но ты уже не уйдёшь.",
        "choices": [
            {"text": "😖 Поскулить. Ждать", "next_scene": "chap2_scene1", "effects": {}},
            {"text": "🧎 Опустить голову к полу", "next_scene": "chap2_scene1", "effects": {}}
        ]
    },

    # ========== ГЛАВА 2 ==========
    "chap2_scene1": {
        "photo": "AgACAgIAAxkBAAIEcGoo3HWZCWWlctChxunj2iI7eDyyAALbGGsbDCFISXynYJA9hkfWAQADAgADeQADOwQ",
        "text": "📍 ГЛАВА 2: ПЕРВЫЙ ТЕСТ 📍\n\nСледующий день. Или час? Ты уже не понимаешь. Богиня Мила сидит на том же месте. Как будто и не вставала.\n\nОна смотрит на тебя с лёгкой улыбкой. Не доброй. Изучающей 😼\n\n— А вот и моя новая шлюшка. Давай посмотрим, чего ты стоишь.\n\nОна указывает пальцем на пол 👇\n\n— Вычистить! Быстро блять!",
        "choices": [
            {"text": "😖 Поскулить. Но подчиниться", "next_scene": "chap2_scene2", "effects": {}},
            {"text": "🧎 Наклониться к полу. Ждать команды", "next_scene": "chap2_scene2", "effects": {}},
            {"text": "😤 Отказаться", "next_scene": "chap2_refuse", "effects": {}}
        ]
    },
    "chap2_refuse": {
        "photo": None,
        "text": "— Ты серьёзно? Убирайся.\n\nБогиня Мила отворачивается. Ты уходишь, униженный.\n\n🏁 ПЛОХАЯ КОНЦОВКА: НЕПОСЛУШАНИЕ\n\n/reset — начать заново",
        "choices": [],
        "set_ending": "bad_early"
    },
    "chap2_scene2": {
        "photo": "AgACAgIAAxkBAAIEdGoo79NlN2AIiEKPUtwmTont3fBPAAIZGWsbDCFIScOehAsnRcQGAQADAgADeQADOwQ",
        "text": "Она скрещивает руки.\n\n— Видишь? Вылижи. Живо. 🦶\n\nТы смотришь на плевок.\n\nТы наклоняешься.",
        "choices": [
            {"text": "👅 Вылизать. Быстро. Стыдливо", "next_scene": "chap2_scene3_success", "effects": {}},
            {"text": "😤 Не буду. Встать", "next_scene": "chap2_refuse", "effects": {}}
        ]
    },
    "chap2_scene3_success": {
        "photo": "AgACAgIAAxkBAAIEdmoo81DgBVSAkv2pidFNGv7tsxwOAAJCGWsbDCFISUBSvUNPnEYKAQADAgADeQADOwQ",
        "text": "Ты лижешь. Пол противный. На вкус — пыль и металл 🤢\n\nБогиня Мила смотрит с отвращением. Но и с интересом.\n\n— Послушный пёсик🐶\n\nТы закрываешь рот. Чувствуешь вкус унижения.",
        "choices": [
            {"text": "😖 Поскулить. Стыдливо отвернуться", "next_scene": "chap2_end", "effects": {}},
            {"text": "😤 Встать и уйти", "next_scene": "chap2_refuse", "effects": {}}
        ]
    },
    "chap2_end": {
        "photo": "AgACAgIAAxkBAAIEeGoo9PIFXCs6_fCvej5NH6uJliXpAAJMGWsbDCFISelozc35O1YPAQADAgADeQADOwQ",
        "text": "Богиня Мила даже не смотрит в твою сторону.\n\n— Свободен. Завтра придёшь — посмотрим, может, я даже не плюну в твою сторону.\n\nТы выползаешь. На улицу дождь 🌧️. Ты мокрый, грязный, униженный.\n\nПочему тебе это нравится?\n\n🏁 КОНЕЦ ГЛАВЫ 2. Ты говно на подошве. Но ты вернёшься.",
        "choices": [
            {"text": "😖 Поскулить. Ждать завтра", "next_scene": "chap3_scene1", "effects": {}},
            {"text": "🧎 Опустить голову. Ползти домой", "next_scene": "chap3_scene1", "effects": {}}
        ]
    },

    # ========== ГЛАВА 3 ==========
    "chap3_scene1": {
        "photo": "AgACAgIAAxkBAAIEemoo_cktmDs-L91xr7f6rGiZu6zPAAJkGWsbDCFISaVYxo4Sos17AQADAgADeQADOwQ",
        "text": "📍 ГЛАВА 3: ЧИСТОТА 📍\n\nТы снова здесь. Богиня Мила сидит, сняв сапог. Её босая нога перед твоим лицом 🦶\n\n— Пол грязный. Вылижешь. Весь. Языком.\n\nОна указывает вокруг.\n\nТы колеблешься.",
        "choices": [
            {"text": "👅 Начать лизать пол", "next_scene": "chap3_scene2", "effects": {}},
            {"text": "😤 Отказаться. Уйти", "next_scene": "chap3_refuse", "effects": {}}
        ]
    },
    "chap3_refuse": {
        "photo": None,
        "text": "— Жалкий трус. Убирайся.\n\n🏁 ПЛОХАЯ КОНЦОВКА\n\n/reset — начать заново",
        "choices": [],
        "set_ending": "bad_early"
    },
    "chap3_scene2": {
        "photo": "AgACAgIAAxkBAAIEfGoo_izgxtKqlzrrR-U8W0jC4TSuAAJlGWsbDCFISchaYqgHlBmmAQADAgADeQADOwQ",
        "text": "Ты лижешь. Подолгу. Язык уже сводит 👅💦. Пол противный, холодный.\n\nБогиня Мила наблюдает. Ей скучно. Или интересно?\n\n— Под ногой тоже. Чисто. Живо.",
        "choices": [
            {"text": "👅 Вылизать под ногой", "next_scene": "chap3_end", "effects": {}},
            {"text": "😤 Не буду", "next_scene": "chap3_refuse", "effects": {}}
        ]
    },
    "chap3_end": {
        "photo": "AgACAgIAAxkBAAIEgGoo_3leVxW_6g0drIYX4Ae-LDN2AAJqGWsbDCFISbH2Pct0d6yqAQADAgADeQADOwQ",
        "text": "Ты лижешь. Горячо. Противно. Твой язык скользит по коже и по полу.\n\nБогиня Мила смотрит на тебя сверху вниз. Её лицо расслаблено.\n\n— Хвалю. Грязнуля. Иди, щенок. Может, не всё потеряно.\n\nОна гладит тебя по голове ✋. Рука холодная. Уверенная.\n\nНо ты чувствуешь тепло. Странное. Грязное. Но тепло.\n\n🏁 КОНЕЦ ГЛАВЫ 3. Ты стал чуть чище. Или ещё грязнее?",
        "choices": [
            {"text": "😖 Поскулить от странного тепла", "next_scene": "chap4_scene1", "effects": {}},
            {"text": "🧎 Остаться у ног. Не уходить", "next_scene": "chap4_scene1", "effects": {}}
        ]
    },

    # ========== ГЛАВА 4 ==========
    "chap4_scene1": {
        "photo": "AgACAgIAAxkBAAIEgmoo_-ThhRQ3akUCFAg48XJ3Wlf1AAJuGWsbDCFISV32lykWZapzAQADAgADeQADOwQ",
        "text": "📍 ГЛАВА 4: САМОНАКАЗАНИЕ 📍\n\nБогиня Мила скрещивает руки на груди. Смотрит строго 😐\n\n— Ты сегодня плохо старался. Отвлёкся. Думал о чём-то своём.\n\nТы замираешь.\n\n— Что с тобой будем делать? Может, ты сам себя накажешь? 🤨",
        "choices": [
            {"text": "🙇 Отшлепать себя при ней", "next_scene": "chap4_end", "effects": {}},
            {"text": "😖 Поскулить. Сжать яйца в кулаке", "next_scene": "chap4_end", "effects": {}},
            {"text": "😤 Я не виноват", "next_scene": "chap4_refuse", "effects": {}}
        ]
    },
    "chap4_refuse": {
        "photo": None,
        "text": "— Ты не жалеешь? Тогда иди нахуй.\n\n🏁 ПЛОХАЯ КОНЦОВКА: БЕЗ РАСКАЯНИЯ\n\n/reset — начать заново",
        "choices": [],
        "set_ending": "bad_early"
    },
    "chap4_end": {
        "photo": "AgACAgIAAxkBAAIEhmopAT7jWHoEwEJqtvOKUqc4Gcn6AAJyGWsbDCFISYOWAetrlCGLAQADAgADeQADOwQ",
        "text": "Богиня Мила разворачивается. Спиной к тебе.\n\n— Запомни это унижение. Ты сам этого хотел. Ты сам выбрал быть здесь.\n\nОна уходит. Ты остаёшься один. На полу. В темноте 🌑\n\nТы слышишь свой голос. Тихо. Скулящий.\n\n🏁 КОНЕЦ ГЛАВЫ 4. Ты ничтожество. Но хотя бы честное.",
        "choices": [
            {"text": "😖 Поскулить в темноте", "next_scene": "chap5_tasks", "effects": {}},
            {"text": "🧎 Ждать. Она вернётся", "next_scene": "chap5_tasks", "effects": {}}
        ]
    },

    # ========== ГЛАВА 5: ЗАДАНИЯ ==========
    "chap5_tasks": {
        "photo": "AgACAgIAAxkBAAIEiGopAb-_Ef6uFYfnPFjYVMeb-c0lAAJ0GWsbDCFISSTu7hquxnPgAQADAgADeQADOwQ",
        "text": "📍 ЗАДАНИЕ ОТ БОГИНИ МИЛЫ 📍\n\nБогиня Мила возвращается и смотрит на тебя.\n\n— Прежде чем продолжить, ты должен доказать свою преданность.\n\n📢 Подпишись на каналы:\n👉 @chat_goddes\n👉 @find_goddes\n\nПосле подписки нажми кнопку ниже.\n\nБогиня Мила проверит.",
        "choices": [
            {"text": "✅ Я подписался на каналы", "next_scene": "chap5_check", "effects": {}},
            {"text": "😖 Пока не готов", "next_scene": "chap5_tasks", "effects": {}}
        ]
    },
    "chap5_check": {
        "photo": None,
        "text": "🔍 Богиня Мила проверяет твою подписку...",
        "choices": []
    },
    "chap5_scene1": {
        "photo": "AgACAgIAAxkBAAIEimopAjRu6AuXMoW0LucHpPDkJrhdAAJ2GWsbDCFISU3V0tDtZSA9AQADAgADeQADOwQ",
        "text": "📍 ГЛАВА 5: ИСКУПЛЕНИЕ 📍\n\nБогиня Мила кивает.\n\n— Хорошо. Ты доказал свою преданность. Я ценю это.\n\nОна подходит ближе.\n\n— Теперь ты готов идти дальше?",
        "choices": [
            {"text": "😖 Да, Богиня. Я готов", "next_scene": "chap5_scene2", "effects": {}},
            {"text": "😤 Я не уверен", "next_scene": "chap5_refuse", "effects": {}}
        ]
    },
    "chap5_refuse": {
        "photo": None,
        "text": "— Жаль. Я думала, из тебя выйдет толк. Уходи.\n\n🏁 ПЛОХАЯ КОНЦОВКА: СОМНЕНИЯ\n\n/reset — начать заново",
        "choices": [],
        "set_ending": "bad_early"
    },
    "chap5_scene2": {
        "photo": "AgACAgIAAxkBAAIEjGopAza8dZJz6W-N0bbCIkGv4ZTsAAJ5GWsbDCFISZRiCiaJ9wvoAQADAgADeQADOwQ",
        "text": "Мила качает головой 🙄\n\n— Молчишь?.. Ладно. Этого конечно мало. Но и на большее ты не способен.\n\nОна подходит. Кладёт руку на твою голову.\n\n— Встань.",
        "choices": [
            {"text": "😖 Поскулить. Встать. Дрожать", "next_scene": "chap5_end", "effects": {}},
            {"text": "🧎 Остаться на коленях", "next_scene": "chap5_end", "effects": {}}
        ]
    },
    "chap5_end": {
        "photo": "AgACAgIAAxkBAAIEjmopBhBKxsRPlduROohQNpaksGzIAAJ_GWsbDCFIScsBzW5v5mvVAQADAgADeQADOwQ",
        "text": "Богиня Мила кивает.\n\n— На колени. Рядом. Может, выйдет из тебя толк.\n\nТы на коленях. Но рядом с ней. Чувствуешь её власть.\n\n— Не подведи.\n\n🏁 КОНЕЦ ГЛАВЫ 5. Один шаг до дна. Или до чего-то другого?",
        "choices": [
            {"text": "😖 Поскулить. Кивнуть", "next_scene": "chap6_final_choice", "effects": {}},
            {"text": "🦶 Умолять прикоснуться к ножкам Богини", "next_scene": "chap6_final_choice", "effects": {}}
        ]
    },

    # ========== ГЛАВА 6 ==========
    "chap6_final_choice": {
        "photo": "AgACAgIAAxkBAAIEkGopBnjz0dnADG1LnE7Qil4Iz2eJAAKBGWsbDCFISVg6EsSjRuABAQADAgADeQADOwQ",
        "text": "📍 ГЛАВА 6: ВЫБОР 📍\n\nБогиня Мила смотрит на тебя. Долго. Изучающе.\n\n— Ты прошёл долгий путь. Многие не доходят. Теперь решай. Что ты выберешь?\n\nОна ждёт. Тишина давит.",
        "choices": [
            {"text": "😖 Подчиниться навсегда. Я Ваш пёс", "next_scene": "chap6_ideal", "effects": {}},
            {"text": "😤 Сказать 'Я устал, Богиня Мила'", "next_scene": "chap6_neutral", "effects": {}},
            {"text": "🦴 Я не выдержу этого..", "next_scene": "chap6_bad", "effects": {}}
        ]
    },

    # ========== ИДЕАЛЬНЫЙ ФИНАЛ ==========
    "chap6_ideal": {
        "photo": "AgACAgIAAxkBAAIEkmopCqw50zk_5wPQ5beFapHmAAGFgAACkxlrGwwhSEnBJSg5RCTKIAEAAwIAA3kAAzsE",
        "text": "🏆 ИДЕАЛЬНЫЙ ФИНАЛ 🏆\n\nБогиня Мила улыбается. Впервые за всё время. Искренне.\n\n— Хороший пёсик. Заслужил.\n\nОна садится на стул, перекидывает ногу на ногу, но ты успеваешь увидеть белоснежные трусики под юбкой, уютно обрисовывая самое желанное, но навсегда недоступное тебе место.\n\n— Подползи. Трогай себя. Я разрешаю. И лижи ножки. Каждый пальчик по отдельности.\n\nТы подползаешь. Рука дрожит. Язык касается её кожи. Она смотрит на тебя сверху вниз.\n\n— Не отводи взгляд.\n\nТы кончаешь под её взглядом 💦. Впервые в жизни ты не чувствуешь стыда. Только благодарность.\n\nОна ставит ногу на твою голову.\n\n— Останься у ног. Твоё место здесь. Ты — мой.\n\n🏆 ПОЗДРАВЛЯЮ! ТЫ ДОСТИГ ИДЕАЛЬНОГО ФИНАЛА 🏆\n\n🤖 БОТ ДЛЯ ПСИН И ДОМИН: @dominasearch24_bot\n\n🎀 Хочешь стать моей сисси? Нажми кнопку ниже!",
        "choices": [
            {"text": "🎀 Стать Сисси", "callback_data": "sissy_access"},
            {"text": "🔄 Пройти заново", "callback_data": "reset_and_play"}
        ],
        "set_ending": "ideal"
    },

    # ========== НЕЙТРАЛЬНЫЙ ФИНАЛ ==========
    "chap6_neutral": {
        "photo": "AgACAgIAAxkBAAIElGopDJTwT8R67lnZKNZSLSGLH321AAKYGWsbDCFISQMCu0d10lWZAQADAgADeQADOwQ",
        "text": "🔸 НЕЙТРАЛЬНЫЙ ФИНАЛ 🔸\n\nБогиня Мила кивает. Без эмоций.\n\n— Я поняла. Ты не готов быть моим псом до конца. Иди. Может, вернёшься, когда созреешь.\n\nОна отворачивается. Ты уходишь под дождь.\n\n— Ты ничего не доказал. Но и не проиграл. Так бывает.\n\nТы выходишь на улицу. Холодно. Одиноко.\n\nНо в груди — странное облегчение.\n\n🔸 НЕЙТРАЛЬНЫЙ ФИНАЛ 🔸\n\n🤖 БОТ ДЛЯ ПСИН И ДОМИН: @dominasearch24_bot",
        "choices": [
            {"text": "🔄 Пройти заново", "callback_data": "reset_and_play"}
        ],
        "set_ending": "neutral"
    },

    # ========== ПЛОХОЙ ФИНАЛ ==========
    "chap6_bad": {
        "photo": "AgACAgIAAxkBAAIElmopDalmqrHYQ4nEoAABDhUWmyHaOQACmhlrGwwhSElinl7o7ySVwQEAAwIAA3kAAzsE",
        "text": "🔻 ПЛОХОЙ ФИНАЛ 🔻\n\nБогиня Мила смотрит с холодом. В глазах — разочарование и брезгливость.\n\n— Ты посмел? Ты — ничтожество. Ты думал, что можешь уйти?\n\nОна встаёт. Подходит ближе.\n\n— Нет. Ты заплатишь.\n\nТвоё наказание: напиши на листе «я ничтожество», сфоткайся на коленях с этим листом и поставь на аву. На неделю.\n\nПридёшь с этим — может, дам второй шанс. Хотя... вряд ли ты достоин даже этого.\n\nОна уходит. Ты остаёшься один. На полу. В пустоте.\n\n🔻 ТЫ ПРОИГРАЛ. ТЫ НИЧТО 🔻\n\n🤖 БОТ ДЛЯ ПСИН И ДОМИН: @dominasearch24_bot",
        "choices": [
            {"text": "🔄 Пройти заново", "callback_data": "reset_and_play"}
        ],
        "set_ending": "bad"
    },

    # ========== ШКОЛА СИССИ ==========
    "sissy_lesson1": {
        "photo": None,
        "text": "🎀 ШКОЛА СИССИ 🎀\n\nУрок 1: Осознание\n\nБогиня Мила смотрит на тебя сверху вниз.\n\n— Ты хочешь быть моей девочкой? Не просто псом, а сисси в кружевах?\n\n— Подумай, прежде чем ответить. Обратной дороги не будет.",
        "choices": [
            {"text": "😊 Да, хочу быть сисси", "next_scene": "sissy_lesson1_yes", "effects": {}},
            {"text": "😤 Нет, я пёс", "next_scene": "sissy_lesson1_no", "effects": {}}
        ]
    },
    "sissy_lesson1_yes": {
        "photo": None,
        "text": "🎀 УРОК 1 ПРОЙДЕН 🎀\n\nБогиня Мила улыбается.\n\n— Хорошая девочка. Ты сделала первый шаг.\n\n— Запомни: сисси не спорит, сисси благодарит, сисси радует.\n\n⬇️ Урок 2: Внешность ⬇️",
        "choices": [
            {"text": "👙 Урок 2", "next_scene": "sissy_lesson2", "effects": {}}
        ]
    },
    "sissy_lesson1_no": {
        "photo": None,
        "text": "Богиня Мила разочарована.\n\n— Тогда зачем ты пришёл? Иди отсюда.",
        "choices": []
    },
    "sissy_lesson2": {
        "photo": None,
        "text": "🎀 УРОК 2: ВНЕШНОСТЬ 🎀\n\nБогиня Мила показывает тебе фото кружевного белья.\n\n— Сисси должна выглядеть как девочка. Кружево, атлас, розовый цвет.\n\n— Выбери свои первые трусики:",
        "choices": [
            {"text": "🌸 Розовые кружевные", "next_scene": "sissy_lesson2_pink", "effects": {}},
            {"text": "🖤 Чёрные атласные", "next_scene": "sissy_lesson2_black", "effects": {}},
            {"text": "❤️ Красные с бантиком", "next_scene": "sissy_lesson2_red", "effects": {}}
        ]
    },
    "sissy_lesson2_pink": {
        "photo": None,
        "text": "🎀 УРОК 2 ПРОЙДЕН 🎀\n\n— Розовый? Мило. Очень по-девичьи.\n\nБогиня Мила одобрительно кивает.\n\n⬇️ Урок 3: Походка и позы ⬇️",
        "choices": [
            {"text": "🦶 Урок 3", "next_scene": "sissy_lesson3", "effects": {}}
        ]
    },
    "sissy_lesson2_black": {
        "photo": None,
        "text": "🎀 УРОК 2 ПРОЙДЕН 🎀\n\n— Чёрный? Смело. Мне нравится.\n\nБогиня Мила одобрительно кивает.\n\n⬇️ Урок 3: Походка и позы ⬇️",
        "choices": [
            {"text": "🦶 Урок 3", "next_scene": "sissy_lesson3", "effects": {}}
        ]
    },
    "sissy_lesson2_red": {
        "photo": None,
        "text": "🎀 УРОК 2 ПРОЙДЕН 🎀\n\n— Красный с бантиком? Очень игриво.\n\nБогиня Мила одобрительно кивает.\n\n⬇️ Урок 3: Походка и позы ⬇️",
        "choices": [
            {"text": "🦶 Урок 3", "next_scene": "sissy_lesson3", "effects": {}}
        ]
    },
    "sissy_lesson3": {
        "photo": None,
        "text": "🎀 УРОК 3: ПОХОДКА И ПОЗЫ 🎀\n\nБогиня Мила встаёт и показывает.\n\n— Сисси двигается плавно, мягко, от бедра. Никакой резкости.\n\n— А теперь правильная поза: на колени, руки за спину, голову опустить.\n\n— Покажи, как ты поняла.",
        "choices": [
            {"text": "🧎 Встать на колени, руки за спину", "next_scene": "sissy_lesson3_correct", "effects": {}},
            {"text": "😤 Я не буду так стоять", "next_scene": "sissy_lesson3_wrong", "effects": {}}
        ]
    },
    "sissy_lesson3_correct": {
        "photo": None,
        "text": "🎀 УРОК 3 ПРОЙДЕН 🎀\n\n— Хорошо. Ты быстро учишься, девочка.\n\nБогиня Мила гладит тебя по голове.\n\n⬇️ Урок 4: Голос и слова ⬇️",
        "choices": [
            {"text": "🗣️ Урок 4", "next_scene": "sissy_lesson4", "effects": {}}
        ]
    },
    "sissy_lesson3_wrong": {
        "photo": None,
        "text": "Богиня Мила хмурится.\n\n— Неправильно. Попробуй ещё раз.",
        "choices": [
            {"text": "🧎 Попробовать снова", "next_scene": "sissy_lesson3", "effects": {}}
        ]
    },
    "sissy_lesson4": {
        "photo": None,
        "text": "🎀 УРОК 4: ГОЛОС И СЛОВА 🎀\n\nБогиня Мила садится напротив.\n\n— Сисси говорит тихо, ласково, с уважением.\n\n— Запомни фразы: «Спасибо, Богиня Мила», «Простите, я была непослушной»\n\n— Повтори хотя бы одну.",
        "choices": [
            {"text": "🙏 Спасибо, Богиня Мила", "next_scene": "sissy_lesson4_correct", "effects": {}},
            {"text": "😤 Не буду", "next_scene": "sissy_lesson4_wrong", "effects": {}}
        ]
    },
    "sissy_lesson4_correct": {
        "photo": None,
        "text": "🎀 УРОК 4 ПРОЙДЕН 🎀\n\n— Умница. Твой голос становится мягче.\n\nБогиня Мила довольно улыбается.\n\n⬇️ Урок 5: Экзамен ⬇️",
        "choices": [
            {"text": "📝 Урок 5", "next_scene": "sissy_lesson5", "effects": {}}
        ]
    },
    "sissy_lesson4_wrong": {
        "photo": None,
        "text": "Богиня Мила вздыхает.\n\n— Неправильно. Попробуй ещё раз.",
        "choices": [
            {"text": "🗣️ Попробовать снова", "next_scene": "sissy_lesson4", "effects": {}}
        ]
    },
    "sissy_lesson5": {
        "photo": None,
        "text": "🎀 УРОК 5: ЭКЗАМЕН 🎀\n\nБогиня Мила садится на трон и смотрит строго.\n\n— Это последний урок. Я проверю, чему ты научилась.\n\n— Как правильно стоять сисси?",
        "choices": [
            {"text": "🧎 На коленях, руки за спиной", "next_scene": "sissy_exam_q2", "effects": {}},
            {"text": "🚶 Стоять как обычно", "next_scene": "sissy_exam_fail", "effects": {}}
        ]
    },
    "sissy_exam_q2": {
        "photo": None,
        "text": "— Хорошо. А что нужно сказать, если ты ошиблась?",
        "choices": [
            {"text": "🙏 Простите, Богиня Мила", "next_scene": "sissy_exam_q3", "effects": {}},
            {"text": "😤 Я не ошибаюсь", "next_scene": "sissy_exam_fail", "effects": {}}
        ]
    },
    "sissy_exam_q3": {
        "photo": None,
        "text": "— Последний вопрос. Какого цвета твои трусики?",
        "choices": [
            {"text": "🌸 Розовые", "next_scene": "sissy_exam_perfect", "effects": {}},
            {"text": "🖤 Чёрные", "next_scene": "sissy_exam_perfect", "effects": {}},
            {"text": "❤️ Красные", "next_scene": "sissy_exam_perfect", "effects": {}}
        ]
    },
    "sissy_exam_perfect": {
        "photo": None,
        "text": "🎀 ПОЗДРАВЛЯЮ! 🎀\n\nБогиня Мила встаёт и подходит ближе.\n\n— Ты прошла обучение, девочка. Теперь ты — моя любимая сисси.\n\nОна надевает на тебя ошейник с розовым бантиком.\n\n— Твоё место — у моих ног. В кружевах. С улыбкой.\n\n🏆 ТЫ СТАЛА ИДЕАЛЬНОЙ СИССИ 🏆\n\n🤖 БОТ ДЛЯ ПСИН И ДОМИН: @dominasearch24_bot",
        "choices": [
            {"text": "🎀 Завершить", "next_scene": "sissy_final_end", "effects": {}}
        ]
    },
    "sissy_exam_fail": {
        "photo": None,
        "text": "🔻 ЭКЗАМЕН ПРОВАЛЕН 🔻\n\nБогиня Мила качает головой.\n\n— Ты не готова. Иди и повтори уроки.",
        "choices": [
            {"text": "📚 Начать заново", "next_scene": "sissy_lesson1", "effects": {}}
        ]
    },
    "sissy_final_end": {
        "photo": None,
        "text": "Ты остаёшься у ног Богини Милы.\n\nТвоё место здесь — в кружевах, с бантиком и улыбкой.\n\nТы — её любимая сисси. Навсегда.\n\n🤖 БОТ ДЛЯ ПСИН И ДОМИН: @dominasearch24_bot",
        "choices": []
    }
}
