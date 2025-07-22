#define FILTERSCRIPT

#include <a_samp>
#include "../include/a_mysql.inc"
#include "../include/Pawn.CMD.inc"

#define BIND_CODE_LEN 7


enum
{
    DIALOG_MAIN,
    DIALOG_INFO,
    DIALOG_BIND,
    DIALOG_CODE
}


enum pdata 
{
    p_accid,
    p_tgbound
}

enum tgdata
{
    t_tg_id,
    t_is_bound,
    t_expire_time
}


new MYSQL:mysql;
new pinfo[MAX_PLAYERS][pdata],tginfo[MAX_PLAYERS][tgdata];
new tgcode[MAX_PLAYERS][BIND_CODE_LEN];
#define COLOR_RED     0xAA3333AA
#define COLOR_GREEN   0x33AA33AA
#define COLOR_YELLOW  0xFFFF00AA
#define SCM SendClientMessage
#define SPD ShowPlayerDialog

#define getaccid(%0) pinfo[%0][p_accid]

public OnFilterScriptInit()
{
    mysql = mysql_connect("localhost", "root", "", "database");
    return 1;
}

public OnFilterScriptExit()
{
    for(new i = 0; i < MAX_PLAYERS; i++)
    {
        if(IsPlayerConnected(i))
        {
            savetg(i);
        }
    }
    mysql_close(mysql);
    return 1;
}





forward checkbind(playerid);
public checkbind(playerid)
{
    new rows, fields, bound[11];
    cache_get_data(rows, fields);
    cache_get_field_content(0, "bound", bound);

    if(strval(bound) > 0)
    {
        SPD(playerid, DIALOG_MAIN, DIALOG_STYLE_MSGBOX, "Telegram Connect",
            "Аккаунт уже привязан", "ОК", "");
        pinfo[playerid][p_tgbound] = true;
    }
    else 
    {
        SPD(playerid, DIALOG_MAIN, DIALOG_STYLE_LIST, "Telegram Connect",
            "1. Информация\n2. Привязать", "Выбрать", "Назад");
        pinfo[playerid][p_tgbound] = false;
    }
    return 1;
}

public OnDialogResponse(playerid, dialogid, response, listitem, inputtext[])
{
    switch(dialogid)
    {
        case DIALOG_BIND:
        {
            if(!response)
            {
                SPD(playerid, DIALOG_MAIN, DIALOG_STYLE_LIST, "Telegram Connect",
                    "1. Информация\n2. Привязать", "Выбрать", "Назад");
                return 1;
            }
            
            switch(listitem)
            {
                case 0:
                {
                    SPD(playerid, DIALOG_CODE, DIALOG_STYLE_INPUT, "Код подтверждения",
                        "Введите код от бота:", "Готово", "Назад");
                }
                case 1:
                {
                    SPD(playerid, DIALOG_INFO, DIALOG_STYLE_MSGBOX, "Инструкция",
                        "1. Найдите бота в тг\n2. Отправьте /getcode\n3. Введите код в игре",
                        "Назад", "");
                }
            }
        }
        
        case DIALOG_CODE:
        {
            if(!response)
            {
                SPD(playerid, DIALOG_BIND, DIALOG_STYLE_LIST, "Привязка",
                    "1. Ввести код\n2. Инструкция", "Выбрать", "Назад");
                return 1;
            }

            new code[7];
            strcat(code, inputtext);

            if(strlen(code) != 6 || !isnumeric(code))
            {
                SCM(playerid, COLOR_RED, "Код должен состоять из 6 цифр");
                SPD(playerid, DIALOG_CODE, DIALOG_STYLE_INPUT, "Код подтверждения",
                    "Введите код от бота:", "Готово", "Назад");
                return 1;
            }
            
            new query[128];
            mysql_format(mysql, query, sizeof(query), 
                "SELECT telegram_id,is_bound,UNIX_TIMESTAMP(code_expires) AS expires \
                FROM telegram_bindings WHERE binding_code='%e' LIMIT 1", code);
            mysql_tquery(mysql, query, "checkcode", "is", playerid, code);
        }
        
        case DIALOG_INFO:
        {
            SPD(playerid, DIALOG_BIND, DIALOG_STYLE_LIST, "Привязка",
                "1. Ввести код\n2. Инструкция", "Выбрать", "Назад");
        }
    }
    return 1;
}

forward checkcode(playerid, const code[]);
public checkcode(playerid, const code[])
{
    new rows, fields;
    cache_get_data(rows, fields);
    
    new acc_id = getaccid(playerid);
    if(acc_id <= 0)
    {
        SCM(playerid, COLOR_RED, "Ошибка ID аккаунта!");
        return 1;
    }
    
    if(rows > 0)
    {
        new temp[32];
        cache_get_field_content(0, "telegram_id", temp, sizeof(temp));
        tginfo[playerid][t_tg_id] = strval(temp);
        
        cache_get_field_content(0, "is_bound", temp, sizeof(temp));
        tginfo[playerid][t_is_bound] = strval(temp);
        
        cache_get_field_content(0, "expires", temp, sizeof(temp));
        tginfo[playerid][t_expire_time] = strval(temp);
        
        if(!tginfo[playerid][t_is_bound] && tginfo[playerid][t_expire_time] > gettime())
        {
            new query[128];
            mysql_format(mysql, query, sizeof(query), 
                "SELECT COUNT(*) as existing FROM telegram_bindings WHERE user_id=%d AND is_bound=1",
                acc_id);
            mysql_tquery(mysql, query, "finalize", "i", playerid);
        }
        else
        {
            SCM(playerid, COLOR_RED, 
                tginfo[playerid][t_is_bound] ? "Код уже использован" : "Код истек");
        }
    }
    else
    {
        SCM(playerid, COLOR_RED, "Неверный код!");
    }
    return 1;
}

forward finalize(playerid);
public finalize(playerid)
{
    new rows, fields, existing[11];
    cache_get_data(rows, fields);
    cache_get_field_content(0, "existing", existing);
    
    if(strval(existing) > 0)
    {
        SCM(playerid, COLOR_RED, "Аккаунт уже привязан!");
        return;
    }
    
    new query[256];
    mysql_format(mysql, query, sizeof(query), 
        "UPDATE telegram_bindings SET is_bound=1,user_id=%d \
        WHERE telegram_id=%d AND binding_code='%e' AND is_bound=0 \
        AND (user_id IS NULL OR user_id=0)", 
        getaccid(playerid), tginfo[playerid][t_tg_id], tgcode[playerid]);
    mysql_tquery(mysql, query, "complete", "i", playerid);
}

forward complete(playerid);
public complete(playerid)
{
    if(cache_affected_rows() > 0)
    {
        new name[MAX_PLAYER_NAME];
        GetPlayerName(playerid, name, sizeof(name));
        
        new query[256];
        mysql_format(mysql, query, sizeof(query), 
            "INSERT INTO telegram_notifications (telegram_id,message,is_sent) \
            VALUES (%d,'Аккаунт привязан!\nНик: %s[%d]',0)", 
            tginfo[playerid][t_tg_id], name, getaccid(playerid));
        mysql_tquery(mysql, query);
        
        SCM(playerid, COLOR_GREEN, "Telegram успешно привязан!");
        pinfo[playerid][p_tgbound] = true;
    }
    else
    {
        SCM(playerid, COLOR_RED, "Ошибка привязки!");
    }
}

forward savetg(playerid);
public savetg(playerid)
{
    new query[128];
    mysql_format(mysql, query, sizeof(query), 
        "UPDATE telegram_bindings SET is_bound=1 WHERE user_id=%d", 
        getaccid(playerid));
    mysql_tquery(mysql, query);
    return 1;
}

stock isnumeric(const string[])
{
    for(new i = 0, j = strlen(string); i < j; i++)
        if(string[i] > '9' || string[i] < '0') return 0;
    return 1;
}
CMD:tg(playerid)
{   
    new query[128];
    mysql_format(mysql, query, sizeof(query), 
        "SELECT COUNT(*) as bound FROM telegram_bindings WHERE user_id=%d AND is_bound=1", 
        getaccid(playerid));
    mysql_tquery(mysql, query, "checkbind", "i", playerid);
    return 1;
}