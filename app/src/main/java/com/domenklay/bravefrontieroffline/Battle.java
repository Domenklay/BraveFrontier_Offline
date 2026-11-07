package com.domenklay.bravefrontieroffline;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.util.List;
import java.util.Random;

/** Standalone, simplified elemental turn-based combat. No server or networking. */
final class Battle {
    final GameData.Mode mode;
    final GameData.Unit[] squad=new GameData.Unit[6];
    final int[] hp=new int[6],bb=new int[6];
    final boolean[] acted=new boolean[6];
    private final Random random=new Random();
    int wave=1, enemyHp,enemyMax,turn=1;
    boolean finished=false,won=false,justWon=false;
    String log="Выберите героя, чтобы атаковать.";

    Battle(GameData data,GameData.Mode stage){
        mode=stage;
        List<GameData.Unit> chosen=data.squad();
        for(int i=0;i<6;i++){squad[i]=chosen.get(i);hp[i]=squad[i].hp;}
        nextEnemy();
    }
    static Battle restore(GameData data,String saved) {
        if(saved==null||saved.isEmpty())return null;
        try {
            JSONObject j=new JSONObject(saved);
            GameData.Mode stage=data.getMode(j.getString("mode"));
            if(stage==null)return null;
            Battle b=new Battle(data,stage);
            b.wave=j.getInt("wave"); b.enemyHp=j.getInt("enemyHp");
            b.enemyMax=j.getInt("enemyMax"); b.turn=j.getInt("turn");
            b.finished=j.optBoolean("finished",false); b.won=j.optBoolean("won",false);
            b.log=j.optString("log","Продолжение боя.");
            JSONArray units=j.getJSONArray("units"),health=j.getJSONArray("hp"),
                    gauge=j.getJSONArray("bb"),action=j.getJSONArray("acted");
            if(units.length()!=6||health.length()!=6||gauge.length()!=6||action.length()!=6)return null;
            for(int i=0;i<6;i++){
                GameData.Unit u=data.getUnit(units.getString(i));
                if(u==null)return null;
                b.squad[i]=u;
                b.hp[i]=Math.max(0,Math.min(u.hp,health.getInt(i)));
                b.bb[i]=Math.max(0,Math.min(100,gauge.getInt(i)));
                b.acted[i]=action.getBoolean(i);
            }
            return b;
        }catch(Exception e){return null;}
    }
    String toJson(){
        try{
            JSONObject j=new JSONObject().put("mode",mode.id).put("wave",wave)
                    .put("enemyHp",enemyHp).put("enemyMax",enemyMax)
                    .put("turn",turn).put("finished",finished).put("won",won).put("log",log);
            JSONArray units=new JSONArray(),health=new JSONArray(),gauge=new JSONArray(),action=new JSONArray();
            for(int i=0;i<6;i++){
                units.put(squad[i].id);health.put(hp[i]);gauge.put(bb[i]);action.put(acted[i]);
            }
            return j.put("units",units).put("hp",health).put("bb",gauge).put("acted",action).toString();
        }catch(JSONException e){return "";}
    }
    private void nextEnemy(){
        enemyMax=mode.enemyHp+(wave-1)*Math.max(20,mode.enemyHp/4);
        enemyHp=enemyMax;
    }
    String enemyElement(){
        String[] cycle={"earth","water","thunder","fire","dark","light"};
        int index=0;
        for(int i=0;i<cycle.length;i++)if(cycle[i].equals(mode.element)){index=i;break;}
        return cycle[(index+wave-1)%cycle.length];
    }
    private static float affinity(String attacker,String defender){
        if(attacker.equals("fire")&&defender.equals("earth"))return 1.5f;
        if(attacker.equals("earth")&&defender.equals("thunder"))return 1.5f;
        if(attacker.equals("thunder")&&defender.equals("water"))return 1.5f;
        if(attacker.equals("water")&&defender.equals("fire"))return 1.5f;
        if(attacker.equals("light")&&defender.equals("dark"))return 1.5f;
        if(attacker.equals("dark")&&defender.equals("light"))return 1.5f;
        if(attacker.equals("earth")&&defender.equals("fire"))return .75f;
        if(attacker.equals("thunder")&&defender.equals("earth"))return .75f;
        if(attacker.equals("water")&&defender.equals("thunder"))return .75f;
        if(attacker.equals("fire")&&defender.equals("water"))return .75f;
        return 1f;
    }
    boolean canAct(int index){return !finished&&index>=0&&index<6&&hp[index]>0&&!acted[index];}
    boolean canBurst(int index){return canAct(index)&&bb[index]>=100;}
    int living(){int n=0;for(int value:hp)if(value>0)n++;return n;}

    void attack(int index,boolean burst){
        justWon=false;
        if(!canAct(index))return;
        boolean useBurst=burst&&bb[index]>=100;
        GameData.Unit unit=squad[index];
        int raw=Math.max(1,unit.atk+(random.nextInt(17)-8));
        int damage=Math.max(1,Math.round(raw*affinity(unit.element,enemyElement())*
                (useBurst?2.7f:1f)));
        enemyHp=Math.max(0,enemyHp-damage);
        if(useBurst)bb[index]=0;else bb[index]=Math.min(100,bb[index]+35);
        acted[index]=true;
        log=unit.name+(useBurst?" использует BB и наносит ":" наносит ")+damage+" урона.";
        if(enemyHp==0){
            if(wave>=mode.waves){
                finished=true;won=true;justWon=true;
                log+=" Победа в режиме «"+mode.name+"»!";
                return;
            }
            wave++;nextEnemy();
            for(int i=0;i<6;i++)acted[i]=false;
            log+=" Новая волна: "+wave+"/"+mode.waves+".";
            return;
        }
        boolean everyone=true;
        for(int i=0;i<6;i++)if(hp[i]>0&&!acted[i])everyone=false;
        if(everyone)enemyTurn();
    }
    private void enemyTurn(){
        int alive=living();
        if(alive==0){finished=true;won=false;return;}
        int selected=random.nextInt(alive);
        int target=0;
        for(int i=0;i<6;i++)if(hp[i]>0 && selected--==0){target=i;break;}
        GameData.Unit victim=squad[target];
        int raw=mode.enemyAtk+(wave-1)*7+random.nextInt(17);
        int damage=Math.max(1,Math.round(raw*affinity(enemyElement(),victim.element))-victim.def/2);
        hp[target]=Math.max(0,hp[target]-damage);
        log+=" Противник атакует "+victim.name+": -"+damage+" HP.";
        turn++;
        for(int i=0;i<6;i++)acted[i]=false;
        if(living()==0){finished=true;won=false;log+=" Отряд побеждён.";}
    }
}
