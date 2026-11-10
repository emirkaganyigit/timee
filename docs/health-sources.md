# Timee içeriklerinin kaynakları

Kaynaklar 9 Kasım 2026 tarihinde kontrol edildi. Uygulama, göz dinlendirme ve nazik hareket hatırlatıcısıdır; görme bozuklukları için tedavi veya kişiye özel egzersiz programı sunmaz.

## Hatırlatma sıklığı

- **Göz: 20 dakika çalışma / doğrulanmış 20 saniye uzağa bakış.** AOA, yaklaşık 6 metre uzaktaki bir nesneye 20 saniye bakmayı önerir. Otomatik göz akışı bu doğrulanmış adımı hiçbir zaman çıkarmaz veya kısaltmaz; ayrıca AAO'nun doğal göz kırpmayı hatırlama rehberini sunan 10 saniyelik bir görsel hatırlatıcı içerir. İki adımın sırası akışlar arasında uzağa bakış → göz kırpma ve göz kırpma → uzağa bakış olarak dönüşür; otomatik göz akışı toplam 30 saniyedir. Uzağa bakış sırasında kullanıcının ekrandaki animasyonu izlemesi gerekmez.
- **Hareket: 60 dakika çalışma / tam 5 dakika ekran dışı mola.** HSE, sık ve kısa molaları önerir; her saat 5–10 dakika örneğini verir. Evrensel tek bir aralık belirtmez. Uygulamanın 60/5 seçimi, bu rehberi ve kullanıcının daha az bölünme isteğini birlikte gözeten ürün varsayılanıdır. Otomatik akış, kaynaklı kısa hareket havuzundan dönüşümlü olarak üç hareket sunar ve kalan süreyi ekran dışı mola olarak tamamlar; hareketler ile kalan süre birlikte her zaman tam 5 dakikadır.
- **Daha sık hareket seçeneği: 30 dakika.** Newcastle NHS iş gününde 30 dakikada bir pozisyon değiştirmeyi önerir. Bu, daha sık hareket etmeyi isteyenler için kaynaklı bir seçenektir.

Varsayılan düzende aynı çalışma periyodunun 20. ve 40. aktif çalışma dakikalarında 30 saniyelik göz akışı; 60. dakikada göz ve hareket akışları tek pencerede sunulur. Birleşik otomatik akış, 30 saniyelik göz adımları ile 5 dakikalık hareket molasının toplamı olarak tam 5 dakika 30 saniyedir.

Hatırlatma kadansı mevcut kesintisiz çalışma periyodundaki aktif süreyi ölçer ve yalnızca sayaç çalışırken ilerler. Beş dakikadan kısa elle duraklatma, aynı çalışma periyodunun donmuş devamı olarak kabul edilir; yeniden başlatıldığında kadans kaldığı yerden sürer. Çalışmanın kesintisiz olarak en az beş dakika durduğu her durumda iki kadans da yeniden başlamadan önce sıfırlanır; bu işlem toplam çalışma süresini değiştirmez ve tamamlanmış mola sayısını artırmaz. Duraklatılmış durum diske kaydedilmişse duvar saati zaman damgası kullanılır; uygulamanın kapalı kaldığı kesintisiz duraklama beş dakikaya ulaştığında da sıfırlama güvenli biçimde uygulanır ve çevrim dışı süre çalışma olarak yazılmaz.

10 saniyelik göz kırpma sunumu, göz adımlarının dönüşümlü sırası, kısa hareketlerin seçimi ve üçlü paketlenmesi, ekran dışı kalan süre ve beş dakikalık kadans sıfırlama eşiği uygulamanın sunum ve zamanlama tercihleridir; doğrulanmış klinik bir protokol değildir. Kütüphaneden elle başlatılan akış yalnızca seçilen tek egzersizi içerir. Kısa hareket adımlarının tamamlanması tek başına 5 dakikalık ekran dışı molanın yerini tutmaz; otomatik akış kalan süreyi ayrıca tamamlar.

## Egzersizlerin kaynakla eşleşmesi

| İçerik | Dayanak |
| --- | --- |
| 20 saniye yaklaşık 6 metre uzağa bakma | AOA 20-20-20 önerisi |
| Doğal göz kırpmayı hatırlama | AAO; belirli tekrar sayısı veya 10 saniyelik klinik doz iddiası yok |
| Ayağa kalkma / kısa yürüyüş / duruş değiştirme | HSE mola rehberi |
| 5 yavaş otur–kalk; 5 destekli topuk kaldırma | NHS Strength exercises |
| Göğüs açma: 5–10 saniye, 5 tekrar | NHS Sitting exercises |
| Omuzları 3 kez öne ve 3 kez geriye çevirme | Newcastle NHS |
| Elleri hafifçe yumruk yapıp parmakları açma: 3 tekrar | Newcastle NHS |

`content.py` içindeki `duration`, animasyon ve rehber ekranı için yaklaşık süredir. Uzağa bakışın kaynakta belirtilen 20 saniyesi dışında bunlar doğrulanmış klinik egzersiz dozları değildir. Otomatik akıştaki sıra değişimi, hareket rotasyonu, üçlü paketleme ve toplam sunum süresi de doğrulanmış bir tedavi ya da egzersiz programı değildir. Kaynakta yer alan tekrar/tutma önerileri `reps` alanında ayrıca belirtilir. Sabit, kaymayan, tekerleksiz sandalye ve rahat hareket aralığı kullanılmalı; ağrı olursa hareket bırakılmalıdır. Kullanıcı hareketi atlayabilmelidir.

## Kanıtın sınırı

Doğru ifade **“AOA, AAO ve NHS rehberlerine dayalı”**dır. Her hareketin her kişide etkili olduğu veya 20-20-20 sayılarının en iyi düzen olduğu iddia edilmez. Mola vermek ve uzağa bakmak kurumların pratik önerileridir; tam sıklık ve sürenin etkisine ilişkin çalışmalar aynı sonucu vermemiştir. Uygulama miyopiyi düzeltme, göz kaslarını güçlendirme veya ekran üstünde şekil takip ederek görmeyi iyileştirme iddiası taşımaz.

## Kaynak bağlantıları

1. [American Optometric Association — Computer vision syndrome / 20-20-20](https://www.aoa.org/healthy-eyes/eye-and-vision-conditions/computer-vision-syndrome/20-20-20-rule?sso=y)
2. [American Academy of Ophthalmology — Computers, Digital Devices, and Eye Strain](https://www.aao.org/eye-health/diseases/computer-usage)
3. [Health and Safety Executive — Work routine and breaks](https://www.hse.gov.uk/msd/dse/work-routine.htm)
4. [NHS — Strength exercises](https://www.nhs.uk/live-well/exercise/strength-exercises/)
5. [NHS — Sitting exercises](https://www.nhs.uk/live-well/exercise/sitting-exercises/)
6. [Newcastle Hospitals NHS — 1 minute body check](https://www.newcastle-hospitals.nhs.uk/services/newcastle-occupational-health-service/information-for-staff/physiotherapy/self-help-leaflets/1-minute-body-check/)
7. [20-20-20 Rule: Are These Numbers Justified? — 2023 araştırması, PubMed](https://pubmed.ncbi.nlm.nih.gov/36473088/)
8. [The effects of breaks on digital eye strain, dry eye and binocular vision: Testing the 20-20-20 rule — PubMed](https://pubmed.ncbi.nlm.nih.gov/35963776/)
